import { useState } from "react";
import type { BaiTuongTuData } from "../types";

/** Bài tập cùng dạng để học sinh tự luyện sau khi đọc xong lời giải.
 *
 * Đáp án CỐ Ý giấu sau một nút bấm. Hiện sẵn thì học sinh đọc luôn con số và bài
 * luyện mất hết tác dụng — mục đích là để các em tự làm trước đã.
 *
 * Đáp án ở đây tin được tuyệt đối: nó do Python tính từ tham số của chính đề bài,
 * không phải do model sinh ra. Vì vậy không có huy hiệu kiểm chứng như đáp án của
 * bài chính — không có gì để nghi ngờ.
 */
export default function BaiTuongTu({
  mon,
  topic,
  cauHoiGoc,
}: {
  mon: string;
  topic: string;
  cauHoiGoc: string;
}) {
  const [bai, setBai] = useState<BaiTuongTuData | null>(null);
  const [dangSinh, setDangSinh] = useState(false);
  const [hienDapAn, setHienDapAn] = useState(false);
  const [hienGoiY, setHienGoiY] = useState(false);
  const [loi, setLoi] = useState("");

  async function sinh() {
    setDangSinh(true);
    setLoi("");
    setHienDapAn(false);
    setHienGoiY(false);
    try {
      const res = await fetch("/api/bai_tuong_tu", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mon, topic, cau_hoi_goc: cauHoiGoc }),
      });
      const data = await res.json();
      if (data.co) setBai(data.bai);
      else {
        setBai(null);
        setLoi(data.ly_do ?? "Không sinh được bài.");
      }
    } catch {
      setLoi("Không gọi được máy chủ.");
    } finally {
      setDangSinh(false);
    }
  }

  return (
    <div className="card bai-tuong-tu">
      <div className="card-head">
        <span className="card-icon">✎</span>
        <h2>Bài tập tương tự</h2>
        <button className="ghost nho" onClick={sinh} disabled={dangSinh}>
          {dangSinh ? "Đang sinh…" : bai ? "Bài khác" : "Sinh bài"}
        </button>
      </div>

      {loi && <p className="ghi-chu">{loi}</p>}

      {bai && (
        <>
          <p className="de-bai">{bai.de_bai}</p>

          <div className="hang-nut">
            {bai.goi_y && (
              <button className="ghost nho" onClick={() => setHienGoiY((v) => !v)}>
                {hienGoiY ? "Ẩn gợi ý" : "Gợi ý"}
              </button>
            )}
            <button className="ghost nho" onClick={() => setHienDapAn((v) => !v)}>
              {hienDapAn ? "Ẩn đáp án" : "Xem đáp án"}
            </button>
            {bai.muc_do && <span className="the-muc">{bai.muc_do}</span>}
          </div>

          {hienGoiY && bai.goi_y && <p className="goi-y">Dùng: {bai.goi_y}</p>}

          {hienDapAn && (
            <p className="dap-an-tuong-tu">
              {bai.dap_an} {bai.don_vi}
            </p>
          )}
        </>
      )}

      {!bai && !loi && (
        <p className="ghi-chu">
          Bấm “Sinh bài” để nhận một bài cùng dạng, đáp án tính bằng công thức nên
          luôn đúng.
        </p>
      )}
    </div>
  );
}
