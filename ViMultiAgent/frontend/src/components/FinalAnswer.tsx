// Kết quả cuối cùng — thứ người dùng tìm trước tiên, nên đặt trên cùng cột phải
// và in to nhất trang.
//
// Kèm luôn trạng thái kiểm chứng: một đáp án chưa qua Verify mà hiển thị y hệt
// đáp án đã qua thì giao diện đang nói dối người dùng.

import type { Verdict } from "../types";

interface Props {
  dapAn: string;
  moTa: string;
  verdict: Verdict | null;
  doTinCay: number | null;
}

const NHAN: Record<Verdict, { chu: string; lop: string }> = {
  PASS: { chu: "Đã kiểm chứng", lop: "ok" },
  FAIL: { chu: "Không qua kiểm chứng", lop: "bad" },
  UNCERTAIN: { chu: "Chưa đủ căn cứ", lop: "warn" },
};

export default function FinalAnswer({ dapAn, moTa, verdict, doTinCay }: Props) {
  if (!dapAn) return null;
  const n = verdict ? NHAN[verdict] : null;

  return (
    <div className="card ket-qua-card">
      <div className="card-head">
        <span className="card-icon">🏆</span>
        <h2>Kết quả cuối cùng</h2>
      </div>

      <div className="dap-an">{dapAn}</div>
      {moTa && <div className="dap-an-mo-ta">{moTa}</div>}

      {(n || doTinCay !== null) && (
        <div className="ket-qua-chan">
          {n && (
            <span className={`nhan ${n.lop}`}>
              {verdict === "PASS" ? "✓" : verdict === "FAIL" ? "✕" : "!"} {n.chu}
            </span>
          )}
          {doTinCay !== null && (
            <span className="tin-cay">Độ tin cậy: {Math.round(doTinCay * 100)}%</span>
          )}
        </div>
      )}
    </div>
  );
}
