"""Lớp trừu tượng LLM — một client duy nhất cho Groq / OpenRouter / Together / Ollama.

Cả bốn đều nói giao thức OpenAI-compatible `/chat/completions`, nên ta chỉ cần httpx,
không cần SDK nào. Đây là lựa chọn có chủ đích: SDK của các nhà cung cấp thay đổi API
liên tục, và một dự án 5 ngày không chịu nổi một lần breaking change.

Ba thứ lớp này lo, ngoài việc gọi model:
  1. CACHE RA ĐĨA  — chạy lại benchmark không tốn thêm tiền. Quan trọng nhất.
  2. NGÂN SÁCH      — ngắt cứng trước khi cháy ví.
  3. JSON BỀN       — LLM trả JSON hỏng là chuyện thường; retry kèm phản hồi lỗi.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from .config import get_settings
from .schemas import AgentSpan

T = TypeVar("T", bound=BaseModel)


class BudgetExceeded(RuntimeError):
    pass


class RateLimited(RuntimeError):
    """Nhà cung cấp chặn vì hết hạn mức. Tách riêng khỏi LLMError để tầng trên
    phân biệt được 'hết quota' với 'model trả lời sai định dạng' — hai thứ này
    cần cách xử lý hoàn toàn khác nhau."""


class LLMError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Bóc JSON khỏi văn bản model trả về
# ---------------------------------------------------------------------------

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)

# Sau dấu `\`, JSON chỉ chấp nhận đúng những ký tự này. Mọi thứ khác là escape hỏng.
_BAD_ESCAPE = re.compile(r'\\(?!["\\/bfnrtu])')


def _fix_latex_escapes(text: str) -> str:
    r"""Nhân đôi các dấu gạch chéo không hợp lệ trong JSON.

    Model sinh LaTeX rất hay viết `\[`, `\alpha`, `\sqrt` với MỘT dấu gạch. `\[` không
    nằm trong danh sách escape hợp lệ của JSON nên `json.loads` ném lỗi và bỏ cả lượt —
    kéo theo 3 lần thử lại của `chat_json`, mỗi lần là một lượt gọi model đầy đủ.
    Đo được trên Groq: một lần hỏng như vậy tốn thêm 30-90 giây.

    Chỉ chạy khi parse chặt ĐÃ thất bại, nên JSON đúng chuẩn không bao giờ bị đụng vào.
    Lưu ý `\t`/`\f` KHÔNG được sửa ở đây vì chúng hợp lệ với JSON — thiệt hại của chúng
    được dọn sau, ở core/latex.py, nơi biết trường nào là LaTeX.
    """
    return _BAD_ESCAPE.sub(r"\\\\", text)


def _parse_fallback(fb: Any) -> dict[str, Any]:
    """Chấp nhận 'provider/model' hoặc dict cấu hình đầy đủ."""
    if isinstance(fb, dict):
        return fb
    prov, _, model = str(fb).partition("/")
    return {"provider": prov, "model": model}


def extract_json(text: str) -> dict[str, Any]:
    """Model hay bọc JSON trong ```json ... ``` hoặc kèm lời dẫn. Cũng có model
    (đặc biệt dòng reasoning) chèn khối <think>...</think> trước. Bóc hết."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    m = _FENCE.search(text)
    if m:
        text = m.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Thử lại sau khi vá escape LaTeX hỏng — rẻ hơn nhiều so với gọi lại model.
    try:
        return json.loads(_fix_latex_escapes(text))
    except json.JSONDecodeError:
        pass

    # Lấy khối {...} cân bằng ngoài cùng.
    start = text.find("{")
    if start == -1:
        raise ValueError(f"Không tìm thấy JSON trong: {text[:200]!r}")
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                blob = text[start : i + 1]
                try:
                    return json.loads(blob)
                except json.JSONDecodeError:
                    # Cùng lý do như ở trên: JSON có lời dẫn bao quanh VÀ có escape
                    # LaTeX hỏng thì phải vá ở đây nữa, nếu không cả nhánh này vô dụng.
                    return json.loads(_fix_latex_escapes(blob))
    raise ValueError(f"JSON không cân bằng ngoặc: {text[:200]!r}")


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class LLMClient:
    def __init__(self, profile: str | None = None) -> None:
        self.s = get_settings()
        self.profile = profile or self.s.profile
        self.cache_dir: Path = self.s.cache_dir
        if self.s.cache_enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.spent_usd = 0.0
        self._sem = asyncio.Semaphore(self.s.max_concurrency)
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> LLMClient:
        timeout = float(self.s.limits.get("llm_timeout_s", 90))
        self._client = httpx.AsyncClient(timeout=timeout)
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            timeout = float(self.s.limits.get("llm_timeout_s", 90))
            self._client = httpx.AsyncClient(timeout=timeout)
        return self._client

    # ---- cache ----------------------------------------------------------

    def _cache_key(self, payload: dict[str, Any], provider: str) -> str:
        blob = json.dumps(
            {"p": provider, **payload}, sort_keys=True, ensure_ascii=False
        )
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]

    def _cache_get(self, key: str) -> dict[str, Any] | None:
        if not self.s.cache_enabled:
            return None
        f = self.cache_dir / f"{key}.json"
        if f.exists():
            try:
                return json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                return None
        return None

    def _cache_put(self, key: str, value: dict[str, Any]) -> None:
        if not self.s.cache_enabled:
            return
        (self.cache_dir / f"{key}.json").write_text(
            json.dumps(value, ensure_ascii=False), encoding="utf-8"
        )

    # ---- gọi model ------------------------------------------------------

    async def chat(
        self,
        agent: str,
        messages: list[dict[str, str]],
        *,
        profile: str | None = None,
        json_mode: bool = False,
        temperature: float | None = None,
        max_tokens: int | None = None,
        model_override: dict[str, Any] | None = None,
        _in_fallback: bool = False,
    ) -> tuple[str, AgentSpan]:
        """Gọi model gán cho `agent`. Trả (text, span đo lường)."""
        cfg = model_override or self.s.agent_model(agent, profile or self.profile)
        provider_name = cfg["provider"]
        model = cfg["model"]
        prov = self.s.provider(provider_name)

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature if temperature is not None else cfg.get("temperature", 0.2),
            "max_tokens": max_tokens or cfg.get("max_tokens", 1500),
        }
        # Model dòng reasoning phát khối <think> trước khi trả lời, nên nhà cung cấp
        # từ chối (HTTP 400) khi bật JSON mode gốc. Với chúng ta tắt cờ này và dựa
        # vào `extract_json`, vốn đã bóc được cả <think> lẫn hàng rào ```json.
        if json_mode and cfg.get("json_mode", True):
            payload["response_format"] = {"type": "json_object"}

        # Token suy luận cũng TÍNH VÀO max_tokens. Với schema dài như của Solver,
        # model có thể tiêu hết ngân sách cho phần suy nghĩ rồi trả content rỗng —
        # đo được: 3 lần thử đều rỗng, mất 93 giây, không ra lời giải nào.
        # Hạ mức suy luận trả lại ngân sách cho phần sinh JSON.
        if cfg.get("reasoning_effort"):
            payload["reasoning_effort"] = cfg["reasoning_effort"]

        span = AgentSpan(agent=agent, model=f"{provider_name}/{model}", started_at=time.time())
        key = self._cache_key(payload, provider_name)

        cached = self._cache_get(key)
        if cached is not None:
            span.cached = True
            span.duration_ms = (time.time() - span.started_at) * 1000.0
            span.prompt_tokens = cached.get("prompt_tokens", 0)
            span.completion_tokens = cached.get("completion_tokens", 0)
            return cached["text"], span

        if self.spent_usd > self.s.budget_usd:
            raise BudgetExceeded(
                f"Đã tiêu ước tính ${self.spent_usd:.2f} > ngân sách ${self.s.budget_usd:.2f}. "
                "Tăng VMA_BUDGET_USD_PER_RUN trong .env nếu cố ý."
            )

        headers = {"Content-Type": "application/json"}
        env = prov.get("api_key_env")
        if env:
            api_key = os.getenv(env)
            if not api_key:
                raise LLMError(
                    f"Thiếu {env} trong .env — provider '{provider_name}' không dùng được. "
                    f"Đặt VMA_PROFILE=local_offline để chạy bằng Ollama."
                )
            headers["Authorization"] = f"Bearer {api_key}"

        url = prov["base_url"].rstrip("/") + "/chat/completions"
        text = ""
        last_err: Exception | None = None

        rate_limited: str | None = None
        async with self._sem:
            for attempt in range(4):
                span.attempts = attempt + 1
                try:
                    client = await self._http()
                    r = await client.post(url, json=payload, headers=headers)
                    if r.status_code == 429:
                        rate_limited = r.text[:300]
                        span.retry_reasons.append("429_rate_limit")
                        # Phân biệt hai loại 429 — chúng đòi cách xử lý ngược nhau:
                        #   TPM (mỗi phút) reset sau vài giây  -> chờ rồi thử lại
                        #   TPD (mỗi ngày) reset sau hàng giờ  -> chờ là vô ích
                        # Không phân biệt thì người dùng ngồi nhìn màn hình trắng
                        # 30 giây (2+4+8+16) rồi vẫn nhận lỗi. Đã xảy ra thật.
                        if "per day" in rate_limited or "TPD" in rate_limited:
                            span.retry_reasons[-1] = "429_per_day_bo_cuoc"
                            break
                        wait = min(2 ** attempt * 2, 20)
                        span.wait_ms += wait * 1000.0
                        await asyncio.sleep(wait)
                        continue
                    r.raise_for_status()
                    data = r.json()
                    text = data["choices"][0]["message"]["content"] or ""
                    usage = data.get("usage") or {}
                    span.prompt_tokens = usage.get("prompt_tokens", 0)
                    span.completion_tokens = usage.get("completion_tokens", 0)
                    break
                except Exception as e:  # noqa: BLE001
                    last_err = e
                    span.retry_reasons.append(f"http_{type(e).__name__}")
                    if attempt == 3:
                        span.ok = False
                        span.error = str(e)[:300]
                        span.duration_ms = (time.time() - span.started_at) * 1000.0
                        raise LLMError(f"[{agent}] gọi {provider_name}/{model} lỗi: {e}") from e
                    span.wait_ms += 1.5 * (attempt + 1) * 1000.0
                    await asyncio.sleep(1.5 * (attempt + 1))

        # Hết lượt thử mà vẫn rỗng. TUYỆT ĐỐI không được trả chuỗi rỗng ra ngoài:
        # nó sẽ nổi lên thành "không tìm thấy JSON", che mất nguyên nhân thật và
        # khiến người dùng đi sửa nhầm chỗ. Đây là lỗi đã thực sự xảy ra.
        if not text.strip():
            if rate_limited:
                fb = cfg.get("fallback")
                if fb and not _in_fallback:
                    print(f"[LLM] {provider_name}/{model} hết quota -> chuyển sang {fb}")
                    # CHỈ mang theo tham số dùng chung được. Các tham số riêng của
                    # một dòng model (reasoning_effort) sẽ khiến model khác trả 400 —
                    # fallback mà lại hỏng thì tệ hơn không có fallback.
                    fb_cfg = {
                        k: v for k, v in cfg.items()
                        if k in ("temperature", "max_tokens", "json_mode")
                    }
                    fb_cfg.update(_parse_fallback(fb))
                    return await self.chat(
                        agent, messages, profile=profile, json_mode=json_mode,
                        temperature=temperature, max_tokens=max_tokens,
                        model_override=fb_cfg, _in_fallback=True,
                    )
                raise RateLimited(
                    f"[{agent}] {provider_name}/{model} đã chạm giới hạn của nhà cung cấp.\n"
                    f"  {rate_limited}\n"
                    f"  Cách xử lý: chờ hạn mức reset · đổi model trong configs/models.yaml "
                    f"· thêm OPENROUTER_API_KEY · hoặc VMA_PROFILE=local_offline (Ollama)."
                )
            raise LLMError(
                f"[{agent}] {provider_name}/{model} trả về nội dung rỗng"
                + (f": {last_err}" if last_err else " (không rõ nguyên nhân).")
            )

        price = self.s.price(model)
        cost = (
            span.prompt_tokens / 1e6 * price.get("in", 0.0)
            + span.completion_tokens / 1e6 * price.get("out", 0.0)
        )
        span.cost_usd = cost
        self.spent_usd += cost
        span.duration_ms = (time.time() - span.started_at) * 1000.0

        # KHÔNG cache phản hồi rỗng. Model dòng reasoning thỉnh thoảng đốt hết
        # max_tokens vào phần suy nghĩ và trả content rỗng; cache lại thì mọi lần
        # thử lại đều ăn đúng cái rỗng đó, biến một sự cố tạm thời thành lỗi vĩnh viễn.
        if text.strip():
            self._cache_put(
                key,
                {
                    "text": text,
                    "prompt_tokens": span.prompt_tokens,
                    "completion_tokens": span.completion_tokens,
                },
            )
        return text, span

    # ---- gọi model và ép về schema -------------------------------------

    async def chat_json(
        self,
        agent: str,
        messages: list[dict[str, str]],
        schema: type[T],
        *,
        profile: str | None = None,
        max_retries: int = 2,
        **kw: Any,
    ) -> tuple[T, list[AgentSpan]]:
        """Gọi model và validate về Pydantic model. Sai schema thì retry KÈM
        thông báo lỗi cụ thể — model sửa được lỗi nó nhìn thấy, không sửa được
        lỗi mơ hồ."""
        spans: list[AgentSpan] = []
        convo = list(messages)

        for attempt in range(max_retries + 1):
            text, span = await self.chat(
                agent, convo, profile=profile, json_mode=True, **kw
            )
            # Đánh dấu NGAY, trước khi biết kết quả: nếu vòng lặp này chạy tới lần 2
            # thì lần 1 đã hỏng, và ta cần thấy điều đó trên timeline. Mỗi lần thử lại
            # là một lượt gọi model đầy đủ — trên Groq đo được 30-90 giây.
            span.meta["schema_attempt"] = attempt + 1
            spans.append(span)
            try:
                return schema.model_validate(extract_json(text)), spans
            except (ValidationError, ValueError, json.JSONDecodeError) as e:
                span.retry_reasons.append(f"schema_{type(e).__name__}")
                span.meta["schema_error"] = str(e)[:200]
                if attempt == max_retries:
                    raise LLMError(
                        f"[{agent}] không trả về JSON hợp lệ sau {max_retries + 1} lần. "
                        f"Lỗi cuối: {str(e)[:300]}"
                    ) from e
                convo = convo + [
                    {"role": "assistant", "content": text[:2000]},
                    {
                        "role": "user",
                        "content": (
                            f"JSON trên KHÔNG hợp lệ. Lỗi: {str(e)[:500]}\n"
                            "Trả lại DUY NHẤT một object JSON hợp lệ, đúng schema đã cho. "
                            "Không giải thích, không markdown, không ```."
                        ),
                    },
                ]
        raise LLMError("unreachable")
