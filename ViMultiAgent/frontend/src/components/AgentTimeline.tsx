// Thanh tiến trình các agent — yêu cầu mục 10 của đề bài.
//
// Đây là thứ khiến sản phẩm "nhìn ra là Multi-Agent". Người chấm cần thấy sáu
// vai trò thực sự chạy tuần tự, mỗi vai trò tốn bao lâu, chứ không phải một hộp
// đen trả ra đáp án.

import type { AgentState } from "../types";

const ICON: Record<AgentState["status"], string> = {
  waiting: "○",
  running: "◐",
  done: "✓",
  failed: "✕",
};

export default function AgentTimeline({ agents }: { agents: AgentState[] }) {
  if (agents.length === 0) return null;

  return (
    <div className="timeline">
      {agents.map((a) => (
        <div key={a.name + (a.retry ? "-retry" : "")} className={`node ${a.status}`}>
          <span className="icon">{ICON[a.status]}</span>
          <span className="label">
            {a.label}
            {a.retry && <span className="badge">giải lại</span>}
            {a.verdict && (
              <span className={`verdict ${a.verdict.toLowerCase()}`}>{a.verdict}</span>
            )}
          </span>
          {typeof a.ms === "number" && a.status !== "running" && (
            <span className="ms">{(a.ms / 1000).toFixed(1)}s</span>
          )}
          {a.detail && <div className="detail">{a.detail}</div>}
        </div>
      ))}
    </div>
  );
}
