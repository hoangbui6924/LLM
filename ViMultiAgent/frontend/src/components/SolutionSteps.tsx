// Lời giải chi tiết.
//
// Hai chế độ, vì hai lúc cần hai thứ khác nhau:
//   * đang chạy  -> chữ chảy về theo dòng từ Explain Agent, người dùng đỡ sốt ruột
//   * chạy xong  -> các bước có cấu trúc từ Subject Agent, gọn và đối chiếu được
//
// Nút "Hiển thị dạng LaTeX" bật tắt việc dựng công thức: học sinh xem bản đã
// dựng, còn người chấm đôi khi cần thấy mã LaTeX thô để kiểm.

import { useState } from "react";
import Markdown from "./Markdown";
import type { SolutionStep } from "../types";

interface Props {
  steps: SolutionStep[];
  markdown: string;
  dangChay: boolean;
}

export default function SolutionSteps({ steps, markdown, dangChay }: Props) {
  const [tho, setTho] = useState(false);
  const coBuoc = steps.length > 0;
  if (!coBuoc && !markdown) return null;

  return (
    <div className="card">
      <div className="card-head">
        <span className="card-icon">📖</span>
        <h2>Lời giải chi tiết</h2>
        {coBuoc && !dangChay && (
          <button
            type="button"
            className="chip-btn"
            onClick={() => setTho((v) => !v)}
          >
            <span className="fx">fx</span>
            {tho ? "Dựng công thức" : "Hiển thị dạng LaTeX"}
          </button>
        )}
      </div>

      {dangChay || !coBuoc ? (
        <div className="giang">
          <Markdown text={markdown} />
          {dangChay && <span className="con-tro" />}
        </div>
      ) : (
        <ol className="buoc">
          {steps.map((s) => (
            <li key={s.id}>
              <span className="so">{s.id}</span>
              <div className="buoc-than">
                {s.goal_vi && <h3>{s.goal_vi}</h3>}
                {s.reason_vi && <p>{s.reason_vi}</p>}
                {s.expression &&
                  (tho ? (
                    <pre className="latex-tho">{s.expression}</pre>
                  ) : (
                    <Markdown text={`$$${s.expression}$$`} />
                  ))}
                {s.result && (
                  <p className="ket-qua">
                    <span>⇒</span> {s.result}
                  </p>
                )}
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
