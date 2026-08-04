"""Nền chung cho mọi agent — dựng trên AutoGen + Ollama.

Kiến trúc là *role specialization*: mọi agent dùng chung một lớp vỏ ở đây, khác
nhau ở system prompt và kiểu dữ liệu trả về. Nhờ vậy thêm một môn học mới chỉ
tốn một file prompt, không phải sửa luồng.

Hai quyết định đáng chú ý:

1. **Buộc đầu ra theo Pydantic.** Mỗi agent khai báo `output_content_type`, Ollama
   trả JSON đúng schema. Không parse văn bản tự do giữa các agent.
2. **Tắt chế độ suy nghĩ của Qwen3.** Chuỗi 5 agent nối tiếp mà để mặc định thì
   riêng phần <think> đã ăn hết ngân sách 45 giây. Chi tiết ở khối ngay bên dưới.
"""

from __future__ import annotations

import asyncio
import contextvars
import time
from typing import Any, AsyncIterator, TypeVar

import ollama
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import ModelClientStreamingChunkEvent
from autogen_ext.models.ollama import OllamaChatCompletionClient
from pydantic import BaseModel, ValidationError

from core import config, json_cuu
from core.schemas import AgentSpan

T = TypeVar("T", bound=BaseModel)


# ---------------------------------------------------------------------------
# Tắt chế độ suy nghĩ của Qwen3 — bắt buộc để đạt mốc 45 giây
# ---------------------------------------------------------------------------
#
# Đo trên máy phát triển, cùng câu hỏi, cùng schema JSON:
#     think bật -> 24,2 giây (khối suy nghĩ 3273 ký tự)
#     think tắt ->  5,1 giây
#
# Ollama tắt bằng tham số `think=False` cho từng lượt gọi, nhưng AutoGen không có
# đường truyền tham số đó xuống: `OllamaChatCompletionClient` chỉ chuyển tiếp
# model, messages, tools, stream, format, options, keep_alive.
#
# Đã thử cách khác — tạo model dẫn xuất với template đóng sẵn <think></think> —
# và cách đó HỎNG: Ollama chỉ áp grammar JSON cho phần sau khối suy nghĩ, nên khi
# khối đó bị đóng sẵn trong prompt, đầu ra trở thành văn xuôi tự do, không còn
# đúng schema. Đừng lặp lại hướng đó.
#
# Cách còn lại là vá ở tầng thư viện `ollama`. Bám vào lớp công khai của ollama
# ổn định hơn là chọc vào thuộc tính nội bộ của AutoGen.
# ContextVar chứ không phải biến toàn cục: các agent chạy song song trong cùng
# một event loop, biến toàn cục sẽ bị lượt này ghi đè lượt kia.
_suy_nghi: contextvars.ContextVar[bool] = contextvars.ContextVar("suy_nghi", default=False)

# Ollama báo lý do dừng qua `done_reason`:
#   "stop"   - model tự kết thúc, bình thường
#   "length" - BỊ CẮT vì chạm trần num_predict
# Không đọc cờ này thì "model bó tay" và "tôi cắt ngang model" rơi vào cùng một
# nhánh xử lý, cùng trả lời giải rỗng, cùng im lặng. Đã mất nửa buổi vì chuyện đó.
# AutoGen không chuyển tiếp cờ, nên bắt ngay tại đây.
_ly_do_dung: contextvars.ContextVar[str] = contextvars.ContextVar("ly_do_dung", default="")
# Giữ lại văn bản thô để còn đường cứu khi Pydantic từ chối bản bị cắt.
_noi_dung_tho: contextvars.ContextVar[str] = contextvars.ContextVar("noi_dung_tho", default="")

_chat_goc = ollama.AsyncClient.chat


async def _chat_co_kiem_soat(self: Any, *args: Any, **kwargs: Any) -> Any:
    kwargs.setdefault("think", _suy_nghi.get())
    kq = await _chat_goc(self, *args, **kwargs)
    try:
        ly_do = getattr(kq, "done_reason", None)
        if ly_do:
            _ly_do_dung.set(str(ly_do))
        noi_dung = getattr(getattr(kq, "message", None), "content", None)
        if noi_dung:
            _noi_dung_tho.set(str(noi_dung))
    except Exception:  # noqa: BLE001 — luồng stream không có thuộc tính này
        pass
    return kq


ollama.AsyncClient.chat = _chat_co_kiem_soat  # type: ignore[method-assign]


def _options(max_tokens: int | None = None) -> dict[str, Any]:
    """Tuỳ chọn sinh cho Ollama.

    `num_predict` là trần cứng cho độ dài đầu ra và là thứ giữ cho SLA không vỡ.
    Khi tắt chế độ suy nghĩ, Qwen3 có xu hướng viết JSON lan man — đo được một
    lượt Planner sinh 1671 token cho việc đáng lẽ chỉ cần 150. Không chặn thì
    một lượt bất thường đủ làm cả luồng trượt mốc 45 giây.
    """
    opt: dict[str, Any] = {
        "temperature": config.TEMPERATURE,
        "num_ctx": config.NUM_CTX,
    }
    if max_tokens:
        opt["num_predict"] = max_tokens
    return opt


# AutoGen chỉ tự suy ra được năng lực của những tên model nó biết sẵn; tên lạ thì
# nó ném ValueError ngay ở hàm khởi tạo. Khai tay để đổi model trong .env không
# phải sửa code.
_MODEL_INFO: dict[str, Any] = {
    "vision": False,
    "function_calling": True,
    "json_output": True,
    "structured_output": True,
    "family": "unknown",
    "multiple_system_messages": True,
}


def make_client(
    model: str,
    response_format: type[BaseModel] | None = None,
    max_tokens: int | None = None,
):
    kw: dict[str, Any] = {
        "model": model,
        "host": config.OLLAMA_HOST,
        "options": _options(max_tokens),
        "model_info": _MODEL_INFO,
    }
    if response_format is not None:
        kw["response_format"] = response_format
    return OllamaChatCompletionClient(**kw)


async def run_structured(
    *,
    name: str,
    system: str,
    task: str,
    out_type: type[T],
    model: str | None = None,
    timeout: float | None = None,
    max_tokens: int | None = None,
) -> tuple[T | None, AgentSpan]:
    """Chạy một agent, ép đầu ra về `out_type`.

    Không ném lỗi ra ngoài: hỏng thì trả `None` kèm span có `ok=False`, để
    Manager tự quyết định đi tiếp hay dừng. Một agent chết không được phép
    kéo sập cả lượt hỏi.
    """
    model = model or config.MODEL_LIGHT
    timeout = timeout or config.AGENT_TIMEOUT
    span = AgentSpan(agent=name, model=model)
    t0 = time.perf_counter()

    # Không truyền `response_format` ở đây: `output_content_type` bên dưới đã
    # đặt schema cho lượt gọi. Đặt cả hai thì AutoGen ném ValueError.
    client = make_client(model, max_tokens=max_tokens)
    token = _suy_nghi.set(name in config.AGENTS_SUY_NGHI)
    token_ld = _ly_do_dung.set("")
    token_nd = _noi_dung_tho.set("")
    try:
        agent = AssistantAgent(
            name=name,
            model_client=client,
            system_message=system,
            output_content_type=out_type,
        )
        result = await asyncio.wait_for(agent.run(task=task), timeout=timeout)
        obj: T | None = None
        for msg in reversed(result.messages):
            content = getattr(msg, "content", None)
            if isinstance(content, out_type):
                obj = content
                break
        if obj is None:
            # Đường cứu: JSON bị cắt vẫn còn phần đầu hoàn chỉnh. Vá lại rồi thử
            # dựng model. Miễn phí về thời gian — không gọi LLM lần nữa, nên
            # không đụng tới ngân sách 90 giây.
            vun = json_cuu.cuu(_noi_dung_tho.get())
            if vun is not None:
                try:
                    obj = out_type.model_validate(vun)
                    span.retry_reasons.append("cuu_json_bi_cat")
                except ValidationError:
                    obj = None

        if obj is None:
            span.ok = False
            if _ly_do_dung.get() == "length":
                # Phân biệt rõ với "model bó tay": đây là lỗi cấu hình của ta.
                span.error = (
                    f"BI CAT vi cham tran num_predict={max_tokens}. "
                    "Noi tran hoac tat che do suy nghi cho agent nay."
                )
                span.retry_reasons.append("truncated")
            else:
                span.error = "khong nhan duoc dau ra dung schema"
        _record_usage(span, result)
        return obj, span
    except asyncio.TimeoutError:
        span.ok = False
        span.error = f"qua han {timeout:.0f}s"
        return None, span
    except Exception as e:  # noqa: BLE001
        span.ok = False
        span.error = f"{type(e).__name__}: {e}"
        return None, span
    finally:
        _suy_nghi.reset(token)
        _ly_do_dung.reset(token_ld)
        _noi_dung_tho.reset(token_nd)
        span.duration_ms = (time.perf_counter() - t0) * 1000.0
        await client.close()


async def stream_text(
    *,
    name: str,
    system: str,
    task: str,
    model: str | None = None,
    timeout: float | None = None,
    max_tokens: int | None = None,
) -> AsyncIterator[str]:
    """Sinh văn bản theo dòng — dùng cho Explain Agent để frontend chạy chữ dần.

    Đây là điểm khác biệt so với `run_structured`: người dùng thấy lời giải hiện
    ra ngay thay vì chờ trọn gói.
    """
    model = model or config.MODEL_LIGHT
    client = make_client(model, max_tokens=max_tokens)
    try:
        agent = AssistantAgent(
            name=name,
            model_client=client,
            system_message=system,
            model_client_stream=True,
        )
        stream = agent.run_stream(task=task)
        deadline = time.perf_counter() + (timeout or config.AGENT_TIMEOUT)
        async for ev in stream:
            if isinstance(ev, ModelClientStreamingChunkEvent) and ev.content:
                yield ev.content
            if time.perf_counter() > deadline:
                break
    except Exception as e:  # noqa: BLE001
        yield f"\n\n_(Explain Agent gặp sự cố: {type(e).__name__})_"
    finally:
        await client.close()


def _record_usage(span: AgentSpan, result: Any) -> None:
    """Gom token đã dùng. AutoGen đặt usage trên từng message."""
    for msg in getattr(result, "messages", []) or []:
        usage = getattr(msg, "models_usage", None)
        if usage:
            span.prompt_tokens += getattr(usage, "prompt_tokens", 0) or 0
            span.completion_tokens += getattr(usage, "completion_tokens", 0) or 0
