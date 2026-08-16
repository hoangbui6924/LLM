import { useEffect, useRef, useState } from "react";
import AgentTimeline from "./components/AgentTimeline";
import BaiTuongTu from "./components/BaiTuongTu";
import FinalAnswer from "./components/FinalAnswer";
import Performance from "./components/Performance";
import SolutionSteps from "./components/SolutionSteps";
import { fetchHealth, solveStream, type Health } from "./api";
import { lamSachToan, laTiengAnh } from "./vanban";
import type {
  AgentName,
  AgentState,
  DapAnEvent,
  SolveResult,
  StreamEvent,
} from "./types";
import "./App.css";

// Thứ tự cố định để thanh tiến trình không nhảy loạn khi sự kiện về. Ba Subject
// Agent dùng chung một ô vì mỗi lượt chỉ chạy đúng một trong ba.
const QUY_TRINH: { name: AgentName; label: string; mo_ta: string }[] = [
  { name: "planner", label: "Planner Agent", mo_ta: "Phân tích và lập kế hoạch giải bài toán" },
  { name: "router", label: "Router Agent", mo_ta: "Chọn tác tử chuyên môn phù hợp" },
  { name: "math_agent", label: "Subject Agent", mo_ta: "Giải bài toán theo chuyên môn" },
  { name: "verify_agent", label: "Verification Agent", mo_ta: "Kiểm tra và xác minh kết quả" },
  { name: "explain_agent", label: "Explanation Agent", mo_ta: "Tạo lời giải chi tiết" },
];

const VI_DU = [
  {
    mon: "Toán",
    de: "Cho hàm số y = (x^2 + 1)/(x - 1). Viết phương trình tiếp tuyến của đồ thị tại điểm có hoành độ x = 2.",
  },
  {
    mon: "Lý",
    de: "Chiếu ánh sáng có bước sóng 0,40 μm vào một kim loại có công thoát 2,2 eV. Biết năng lượng photon là 3,1 eV. Động năng ban đầu cực đại của electron quang điện là",
  },
  {
    mon: "Hoá",
    de: "Đốt cháy hoàn toàn 5,6 gam Fe trong khí O2 dư thu được Fe3O4. Tính khối lượng Fe3O4 thu được.",
  },
];

/** Bóc mục "Dễ sai ở đâu" khỏi lời giảng để dựng thành thẻ riêng.
 *
 * Bốn chốt chặn, mỗi cái đến từ một lần hỏng thật quan sát được trên giao diện:
 *
 * 1. **Cắt khối `<think>` trước.** Model đôi khi nhắc lại tiêu đề "Dễ sai ở đâu"
 *    ngay trong lúc suy nghĩ. Bắt trúng chỗ đó thì toàn bộ lời giảng phía sau bị
 *    đổ vào thẻ, kể cả thẻ đóng `</think>`.
 * 2. **Lấy lần xuất hiện CUỐI CÙNG**, không phải lần đầu — vì mục này luôn nằm
 *    cuối lời giảng.
 * 3. **Chỉ nhận dòng gạch đầu dòng.** Nội dung thật luôn là danh sách; mọi thứ
 *    khác (tiêu đề, đoạn văn, công thức `$$`) đều bị loại.
 * 4. **Chấp nhận cả `*Dễ sai ở đâu**` lẫn `**Dễ sai ở đâu**`** — model sinh thiếu
 *    một dấu sao là chuyện thường gặp.
 *
 * Sau khi bóc còn hai bước dọn, xem `vanban.ts`: hạ LaTeX xuống chữ thường
 * (thẻ này không dựng công thức) và bỏ những dòng model lỡ viết tiếng Anh.
 */

function bocLuuY(md: string): string[] {
  const sach = md
    .replace(/<think>[\s\S]*?<\/think>/gi, "")
    .replace(/<\/?think>/gi, "");

  const cac = [...sach.matchAll(/\*{1,2}\s*Dễ sai ở đâu\s*\*{1,2}/gi)];
  if (cac.length === 0) return [];
  const cuoi = cac[cac.length - 1];

  return sach
    .slice((cuoi.index ?? 0) + cuoi[0].length)
    .split("\n")
    .filter((l) => /^\s*[-*•]\s+/.test(l))
    .map((l) => l.replace(/^\s*[-*•]\s+/, "").trim())
    .filter((l) => l.length > 2 && !l.includes("**"))
    .map(lamSachToan)
    .filter((l) => l.length > 2 && !laTiengAnh(l));
}

export default function App() {
  const [question, setQuestion] = useState("");
  const [running, setRunning] = useState(false);
  const [agents, setAgents] = useState<AgentState[]>([]);
  const [answer, setAnswer] = useState("");
  const [ketQua, setKetQua] = useState<SolveResult | null>(null);
  // Đáp án về TRƯỚC lời giảng. Giữ riêng để hiện ngay, thay vì chờ sự kiện `done`
  // vốn chỉ đến sau khi Explain Agent giảng xong (~10 giây sau).
  const [dapAnSom, setDapAnSom] = useState<DapAnEvent | null>(null);
  const [totalMs, setTotalMs] = useState(0);
  const [withinSla, setWithinSla] = useState<boolean | null>(null);
  const [warning, setWarning] = useState("");
  const [sympyFixes, setSympyFixes] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [health, setHealth] = useState<Health | null>(null);
  const [toi, setToi] = useState(() => localStorage.getItem("vma-theme") === "dark");
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    fetchHealth().then(setHealth);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = toi ? "dark" : "light";
    localStorage.setItem("vma-theme", toi ? "dark" : "light");
  }, [toi]);

  function reset() {
    setAgents(QUY_TRINH.map((a) => ({ ...a, status: "waiting" as const })));
    setAnswer("");
    setKetQua(null);
    setDapAnSom(null);
    setTotalMs(0);
    setWithinSla(null);
    setWarning("");
    setSympyFixes([]);
    setError("");
  }

  function applyEvent(ev: StreamEvent) {
    switch (ev.type) {
      case "agent": {
        setAgents((prev) => {
          const next = [...prev];
          const laSubject =
            ev.name !== "verify_agent" &&
            ev.name !== "explain_agent" &&
            ev.name.endsWith("_agent");
          const o = laSubject ? "math_agent" : ev.name;
          const i = next.findIndex((a) => a.name === o);
          if (i === -1) return prev;
          next[i] = {
            ...next[i],
            label: laSubject ? ev.label : next[i].label,
            mo_ta:
              ev.name === "router" && ev.detail
                ? ev.detail.split("—")[0].trim()
                : next[i].mo_ta,
            status:
              ev.status === "start" ? "running" : ev.ok === false ? "failed" : "done",
            ms: ev.ms ?? next[i].ms,
            detail: ev.detail ?? next[i].detail,
            verdict: ev.verdict ?? next[i].verdict,
            retry: ev.retry ?? next[i].retry,
          };
          return next;
        });
        break;
      }
      case "token":
        setAnswer((prev) => prev + ev.text);
        break;
      case "retry":
        setWarning(`Verify bắt lỗi, Subject Agent giải lại lần ${ev.round}: ${ev.reason}`);
        break;
      case "arbiter":
        setSympyFixes(ev.items);
        break;
      case "dap_an":
        setDapAnSom(ev);
        if (ev.warning) setWarning(ev.warning);
        break;
      case "cuu_dap_an":
        setWarning(
          `Đáp án ${ev.gia_tri} do công cụ tính trực tiếp từ đề (${ev.cach_lam}), ` +
            "vì lời giải từng bước không qua được kiểm chứng.",
        );
        break;
      case "done":
        setTotalMs(ev.total_ms);
        setWithinSla(ev.within_sla);
        setKetQua(ev.result);
        if (ev.warning) setWarning(ev.warning);
        break;
      case "error":
        setError(ev.message);
        break;
    }
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const q = question.trim();
    if (!q || running) return;
    reset();
    setRunning(true);
    abortRef.current = new AbortController();
    try {
      for await (const ev of solveStream(q, abortRef.current.signal)) applyEvent(ev);
    } catch (err) {
      if ((err as Error).name !== "AbortError") setError((err as Error).message);
    } finally {
      setRunning(false);
    }
  }

  const sol = ketQua?.solution ?? null;
  // Ưu tiên kết quả đầy đủ khi đã có; trước đó thì dùng đáp án về sớm. Nhờ vậy
  // người dùng đọc được đáp số ngay khi nó chốt, không phải chờ giảng bài xong.
  const dapAn = sol?.final_answer || dapAnSom?.gia_tri || "";
  const moTaDapAn =
    ketQua?.plan?.unknowns?.[0]?.description_vi ||
    ketQua?.plan?.unknowns?.[0]?.symbol ||
    "";
  const luuY = bocLuuY(answer);
  const daChay = agents.some((a) => a.status !== "waiting");

  const chips = [
    { ten: health?.model_heavy ?? "Qwen3", bat: !!health, mau: "c1" },
    { ten: "PhoBERT", bat: ketQua?.route?.decided_by === "phobert" || !daChay, mau: "c2" },
    { ten: "SymPy", bat: health?.tools?.sympy ?? false, mau: "c3" },
    { ten: "Verification Engine", bat: true, mau: "c4" },
  ];

  return (
    <div className="app">
      <header className="topbar">
        <div>
          <h1>ViMultiAgent</h1>
          <p className="sub">Hệ thống đa tác tử giải bài tập STEM bằng tiếng Việt</p>
        </div>
        <div className="topbar-right">
          <span className={`he-thong ${health ? "ok" : "bad"}`}>
            <i /> {health ? "Hệ thống sẵn sàng" : "Không kết nối được backend"}
          </span>
          <button
            type="button"
            className="icon-btn"
            onClick={() => setToi((v) => !v)}
            title={toi ? "Chuyển nền sáng" : "Chuyển nền tối"}
          >
            {toi ? "☀" : "☾"}
          </button>
        </div>
      </header>

      <div className="chips">
        {chips.map((c) => (
          <span key={c.ten} className={`chip ${c.mau} ${c.bat ? "" : "tat"}`}>
            <i /> {c.ten}
          </span>
        ))}
      </div>

      <div className="grid">
        <div className="cot">
          <div className="card">
            <div className="card-head">
              <span className="card-icon">💬</span>
              <h2>Nhập câu hỏi của bạn</h2>
            </div>
            <form onSubmit={onSubmit}>
              <textarea
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Nhập câu hỏi Toán, Vật lý hoặc Hoá học…"
                rows={4}
                disabled={running}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) onSubmit(e);
                }}
              />
              <div className="actions">
                <div className="vi-du">
                  {VI_DU.map((v) => (
                    <button
                      key={v.mon}
                      type="button"
                      className="chip-btn"
                      disabled={running}
                      onClick={() => setQuestion(v.de)}
                    >
                      {v.mon}
                    </button>
                  ))}
                </div>
                <div className="actions-right">
                  <span className="hint">Ctrl + Enter</span>
                  {running && (
                    <button
                      type="button"
                      className="ghost"
                      onClick={() => abortRef.current?.abort()}
                    >
                      Dừng
                    </button>
                  )}
                  <button
                    type="submit"
                    className="primary"
                    disabled={running || !question.trim()}
                  >
                    {running ? "Đang giải…" : "✦ Giải bài"}
                  </button>
                </div>
              </div>
            </form>
          </div>

          <AgentTimeline agents={agents} />

          {totalMs > 0 && (
            <Performance agents={agents} totalMs={totalMs} />
          )}

          {totalMs > 0 && withinSla !== null && (
            <div className={`sla ${withinSla ? "ok" : "over"}`}>
              Tổng thời gian {(totalMs / 1000).toFixed(1)}s — {withinSla ? "đạt" : "vượt"}{" "}
              mốc {health?.sla_seconds ?? 150} giây
            </div>
          )}
        </div>

        <div className="cot">
          <FinalAnswer dapAn={dapAn} moTa={moTaDapAn} />

          {error && <div className="bang err">Lỗi: {error}</div>}
          {warning && <div className="bang warn">{warning}</div>}
          {sympyFixes.length > 0 && (
            <div className="bang fixed">
              <strong>SymPy đã sửa {sympyFixes.length} bước tính sai</strong>
              <ul>
                {sympyFixes.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
          )}

          <SolutionSteps steps={sol?.steps ?? []} markdown={answer} dangChay={running} />
        </div>

        {/* Cột 3 — phần học thêm sau khi đã đọc xong lời giải. Tách riêng để lời
            giải ở cột giữa không bị đẩy dài thêm, và để hai thẻ này nằm ngang tầm
            mắt thay vì phải cuộn xuống cuối trang mới thấy. */}
        <div className="cot cot-phu">
          {!running && totalMs > 0 && (
            <BaiTuongTu
              mon={ketQua?.plan?.subject ?? ketQua?.route?.subject ?? "math"}
              topic={ketQua?.plan?.topic ?? ""}
              cauHoiGoc={ketQua?.question ?? ""}
            />
          )}

          {luuY.length > 0 && !running && (
            <div className="card luu-y">
              <div className="card-head">
                <span className="card-icon">⚠</span>
                <h2>Lưu ý thường gặp</h2>
              </div>
              <ul>
                {luuY.map((l, i) => (
                  <li key={i}>{l}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
