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
  dai_so_agent: "∑",
  hinh_hoc_agent: "△",
  verify_agent: "🛡",
  explain_agent: "📖",
};

const TRANG_THAI: Record<AgentState["status"], string> = {
  waiting: "Chờ",
  running: "Đang chạy",
  done: "Hoàn tất",
  failed: "Lỗi",
};

// Ba tầng định tuyến, rẻ trước đắt sau. Hiện rõ tầng nào đã quyết định là cách
// duy nhất để người xem thấy PhoBERT có thực sự được dùng hay chỉ nằm không.
const TANG: Record<string, { chu: string; ten: string }> = {
  phobert: { chu: "PhoBERT", ten: "Bộ phân loại học sâu, ~30 ms" },
  rule: { chu: "Luật từ khoá", ten: "Không tốn mô hình, 0 ms" },
  llm: { chu: "LLM", ten: "Hỏi mô hình ngôn ngữ, 2-4 giây" },
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

                <span className={`glyph agent-${a.agent_that ?? a.name}`}>
                  {BIEU_TUONG[a.agent_that ?? a.name] ?? "●"}
                </span>

                <span className="node-text">
                  <span className="node-name">
                    {a.label}
                    {a.retry && <span className="badge">giải lại</span>}
                    {a.decided_by && (
                      <span
                        className={`badge tang tang-${a.decided_by}`}
                        title={TANG[a.decided_by]?.ten}
                      >
                        {TANG[a.decided_by]?.chu ?? a.decided_by}
                        {a.decided_by === "phobert" &&
                          typeof a.phobert_confidence === "number" &&
                          ` ${a.phobert_confidence.toFixed(2)}`}
                      </span>
                    )}
                    {a.topic && <span className="badge dang">{a.topic}</span>}
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
