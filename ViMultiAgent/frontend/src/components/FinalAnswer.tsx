// Kết quả cuối cùng — thứ người dùng tìm trước tiên, nên đặt trên cùng cột phải
// và in to nhất trang.
//
// Kèm luôn trạng thái kiểm chứng: một đáp án chưa qua Verify mà hiển thị y hệt
// đáp án đã qua thì giao diện đang nói dối người dùng.

import type { Verdict } from "../types";

// Cố ý KHÔNG hiện "độ tin cậy": con số đó do chính model 4B tự khai, và khi lời
// giải bị bắt lỗi nó còn bị nâng lên 0,8 — nghĩa là "chắc chắn 80% rằng bài này
// SAI". Đặt cạnh đáp án thì người đọc hiểu ngược hoàn toàn. Nhãn kiểm chứng bên
// dưới mới là thứ có căn cứ, vì nó đến từ các phép kiểm tất định.
interface Props {
  dapAn: string;
  moTa: string;
  verdict: Verdict | null;
}

const NHAN: Record<Verdict, { chu: string; lop: string }> = {
  PASS: { chu: "Đã kiểm chứng", lop: "ok" },
  FAIL: { chu: "Không qua kiểm chứng", lop: "bad" },
  UNCERTAIN: { chu: "Chưa đủ căn cứ", lop: "warn" },
};

export default function FinalAnswer({ dapAn, moTa, verdict }: Props) {
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

      {n && (
        <div className="ket-qua-chan">
          <span className={`nhan ${n.lop}`}>
            {verdict === "PASS" ? "✓" : verdict === "FAIL" ? "✕" : "!"} {n.chu}
          </span>
        </div>
      )}
    </div>
  );
}
