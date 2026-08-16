// Kết quả cuối cùng — thứ người dùng tìm trước tiên, nên đặt trên cùng cột phải
// và in to nhất trang.
//
// Cố ý KHÔNG hiện "độ tin cậy" lẫn nhãn kiểm chứng ở đây: con số tin cậy do
// chính model 4B tự khai, còn nhãn kiểm chứng đã nằm sẵn ở dòng Verification
// Agent bên cột trái. Nhắc lại dưới đáp án chỉ làm người đọc phân vân.
interface Props {
  dapAn: string;
  moTa: string;
}

export default function FinalAnswer({ dapAn, moTa }: Props) {
  if (!dapAn) return null;

  return (
    <div className="card ket-qua-card">
      <div className="card-head">
        <span className="card-icon">🏆</span>
        <h2>Kết quả cuối cùng</h2>
      </div>

      <div className="dap-an">{dapAn}</div>
      {moTa && <div className="dap-an-mo-ta">{moTa}</div>}
    </div>
  );
}
