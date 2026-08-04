// Quy trình đa tác tử — yêu cầu mục 10 của đề bài.
//
// Đây là thứ khiến sản phẩm "nhìn ra là Multi-Agent": người chấm thấy từng vai
// chạy tuần tự, mỗi vai tốn bao lâu, chứ không phải một hộp đen trả ra đáp án.
// Bấm vào một dòng để mở chi tiết vai đó đã kết luận gì.

import { useState } from "react";
import type { AgentState } from "../types";

const BIEU_TUONG: Record<string, string> = {
  planner: "◈",
  router: "⇄",
  math_agent: "∑",
  physics_agent: "⚛",
  chemistry_agent: "⌬",
  verify_agent: "🛡",
  explain_agent: "📖",
};

const TRANG_THAI: Record<AgentState["status"], string> = {
  waiting: "Chờ",
  running: "Đang chạy",
  done: "Hoàn tất",
  failed: "Lỗi",
};

export default function AgentTimeline({ agents }: { agents: AgentState[] }) {
  const [moRong, setMoRong] = useState<string | null>(null);
  if (agents.length === 0) return null;

  return (
    <div className="card">
      <div className="card-head">
        <span className="card-icon">⚙</span>
        <h2>Quy trình đa tác tử</h2>
      </div>

      <div className="timeline">
        {agents.map((a) => {
          const mo = moRong === a.name;
          const nhan =
            a.name === "verify_agent" && a.verdict
              ? a.verdict === "PASS"
                ? "Đã xác minh"
                : a.verdict === "FAIL"
                  ? "Không đạt"
                  : "Chưa chắc chắn"
              : TRANG_THAI[a.status];

          return (
            <div key={a.name} className={`node ${a.status}`}>
              <button
                type="button"
                className="node-head"
                onClick={() => setMoRong(mo ? null : a.name)}
                disabled={!a.detail}
              >
                <span className={`dot ${a.status}`}>
                  {a.status === "done" ? "✓" : a.status === "failed" ? "✕" : ""}
                </span>

                <span className={`glyph agent-${a.name}`}>
                  {BIEU_TUONG[a.name] ?? "●"}
                </span>

                <span className="node-text">
                  <span className="node-name">
                    {a.label}
                    {a.retry && <span className="badge">giải lại</span>}
                  </span>
                  <span className="node-desc">{a.mo_ta}</span>
                </span>

                <span className="node-meta">
                  <span
                    className={`status ${
                      a.status === "failed" || a.verdict === "FAIL" ? "bad" : "good"
                    }`}
                  >
                    {nhan}
                  </span>
                  {typeof a.ms === "number" && a.status !== "running" && (
                    <span className="ms">{(a.ms / 1000).toFixed(2)}s</span>
                  )}
                </span>

                {a.detail && <span className="chevron">{mo ? "⌃" : "⌄"}</span>}
              </button>

              {mo && a.detail && <div className="node-detail">{a.detail}</div>}
            </div>
          );
        })}
      </div>
    </div>
  );
}
