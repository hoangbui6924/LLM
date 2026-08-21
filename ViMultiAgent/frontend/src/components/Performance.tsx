// Hiệu suất xử lý — cho thấy thời gian đi đâu.
//
// Với KPI 150 giây, biết vai nào ăn hết ngân sách là thông tin quan trọng nhất
// khi tối ưu. Thanh xếp chồng đọc nhanh hơn bảng số.

import type { AgentState } from "../types";

const MAU: Record<string, string> = {
  planner: "var(--c-planner)",
  router: "var(--c-router)",
  dai_so_agent: "var(--c-subject)",
  hinh_hoc_agent: "var(--c-subject)",
  verify_agent: "var(--c-verify)",
  explain_agent: "var(--c-explain)",
};

interface Props {
  agents: AgentState[];
  totalMs: number;
}

export default function Performance({ agents, totalMs }: Props) {
  const muc = agents.filter((a) => typeof a.ms === "number" && a.ms > 0);
  if (muc.length === 0 || totalMs <= 0) return null;

  // Chia theo tổng thời gian THẬT, không theo tổng các vai: chênh lệch chính là
  // phần chi phí điều phối, giấu đi thì bảng số không cộng lại đúng 100%.
  const phanTram = (ms: number) => (ms / totalMs) * 100;

  return (
    <div className="card">
      <div className="card-head">
        <span className="card-icon">⚡</span>
        <h2>Hiệu suất xử lý</h2>
        <span className="head-note">Tổng thời gian: {(totalMs / 1000).toFixed(2)}s</span>
      </div>

      <div className="perf">
        <div className="perf-left">
          <div className="bar">
            {muc.map((a) => (
              <span
                key={a.name}
                className="seg"
                style={{
                  width: `${phanTram(a.ms!)}%`,
                  background: MAU[a.name] ?? "var(--muted)",
                }}
                title={`${a.label}: ${(a.ms! / 1000).toFixed(2)}s`}
              />
            ))}
          </div>

          <div className="perf-grid">
            {muc.map((a) => (
              <div key={a.name} className="perf-item">
                <span
                  className="tick"
                  style={{ background: MAU[a.name] ?? "var(--muted)" }}
                />
                <span className="perf-name">{a.label}</span>
                <span className="perf-pct">{phanTram(a.ms!).toFixed(0)}%</span>
                <span className="perf-ms">{(a.ms! / 1000).toFixed(2)}s</span>
              </div>
            ))}
          </div>
        </div>

      </div>
    </div>
  );
}
