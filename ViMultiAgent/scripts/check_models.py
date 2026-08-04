"""Kiểm tra mọi model trong configs/models.yaml có thật sự dùng được không.

    python scripts/check_models.py
    python scripts/check_models.py --profile cloud_default

Chạy cái này TRƯỚC mỗi lần benchmark lớn và trước buổi bảo vệ. Danh mục model của
các nhà cung cấp thay đổi liên tục — phát hiện `model_not_found` ở đây mất 10 giây,
phát hiện nó giữa lúc chạy ablation mất cả buổi tối.

Script cũng kiểm tra ràng buộc bất biến của đề tài: **solver và verifier phải khác họ**.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vimultiagent.core.config import get_settings  # noqa: E402
from vimultiagent.core.llm import LLMClient, extract_json  # noqa: E402

PROBE = [
    {"role": "system", "content": 'Trả lời DUY NHẤT bằng JSON: {"ok": true, "answer": "..."}'},
    {"role": "user", "content": "2 + 2 bằng mấy? Trả lời ngắn gọn."},
]


def family(model: str) -> str:
    """Suy ra họ model từ tên. Thô nhưng đủ để bắt vi phạm ràng buộc khác-họ."""
    m = model.lower()
    for key, fam in (
        ("gpt-oss", "gpt-oss"), ("llama", "llama"), ("qwen", "qwen"),
        ("deepseek", "deepseek"), ("mixtral", "mistral"), ("mistral", "mistral"),
        ("gemma", "gemma"), ("kimi", "moonshot"),
    ):
        if key in m:
            return fam
    return m.split("/")[-1].split("-")[0]


async def main_async(profile: str | None) -> int:
    s = get_settings()
    profiles = [profile] if profile else list(s.models.get("profiles", {}))

    print("Provider khả dụng:", s.available_providers(), "\n")
    bad = 0

    for prof in profiles:
        print(f"{'=' * 74}\nProfile: {prof}\n{'=' * 74}")
        block = s.models["profiles"][prof]
        seen: dict[str, tuple[str, float, int]] = {}

        async with LLMClient(profile=prof) as client:
            for agent in block:
                cfg = s.agent_model(agent, prof)
                model = cfg["model"]
                prov = cfg["provider"]

                if not s.available_providers().get(prov):
                    print(f"  ⊘ {agent:<18} {prov}/{model:<28} provider chưa cấu hình")
                    continue

                if model in seen:
                    ms, tok = seen[model][1], seen[model][2]
                    print(f"  ✓ {agent:<18} {prov}/{model:<28} (đã kiểm) {ms:6.0f}ms")
                    continue

                t = time.time()
                try:
                    text, span = await client.chat(
                        agent, PROBE, profile=prof, json_mode=True, max_tokens=200
                    )
                    ms = (time.time() - t) * 1000
                    try:
                        extract_json(text)
                        js = "json ✓"
                    except Exception:  # noqa: BLE001
                        js = "json ✗ (đặt json_mode: false)"
                        bad += 1
                    tok = span.completion_tokens
                    print(f"  ✓ {agent:<18} {prov}/{model:<28} {ms:6.0f}ms  {tok:>4} tok  {js}")
                    seen[model] = (js, ms, tok)
                except Exception as e:  # noqa: BLE001
                    bad += 1
                    print(f"  ✗ {agent:<18} {prov}/{model:<28} LỖI: {str(e)[:80]}")

        # ---- ràng buộc bất biến của đề tài ----
        solver_fams = {
            family(s.agent_model(a, prof)["model"]) for a in block if a.startswith("solver_")
        }
        ver_fam = family(s.agent_model("verifier", prof)["model"]) if "verifier" in block else None
        if ver_fam and ver_fam in solver_fams:
            marker = "CỐ Ý (đây là ablation A3)" if "same_family" in prof else "⚠ VI PHẠM"
            print(f"\n  {marker}: verifier cùng họ '{ver_fam}' với solver.")
            if "same_family" not in prof:
                bad += 1
        else:
            print(f"\n  ✓ Khác họ: solver={solver_fams} vs verifier={{{ver_fam}}}")
        print()

    print(f"{'=' * 74}")
    print("Tất cả model đều dùng được." if bad == 0 else f"⚠ {bad} vấn đề cần sửa.")
    return 0 if bad == 0 else 1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default=None)
    raise SystemExit(asyncio.run(main_async(ap.parse_args().profile)))


if __name__ == "__main__":
    main()
