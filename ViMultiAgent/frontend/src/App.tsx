import { useEffect, useRef, useState } from "react";
import AgentTimeline from "./components/AgentTimeline";
import Markdown from "./components/Markdown";
import { fetchHealth, solveStream, type Health } from "./api";
import type { AgentState, AgentName, StreamEvent } from "./types";
import "./App.css";

// Thứ tự cố định để thanh tiến trình không nhảy loạn khi sự kiện về.
const ORDER: { name: AgentName; label: string }[] = [
  { name: "planner", label: "Planner" },
  { name: "router", label: "Router" },
  { name: "math_agent", label: "Subject Agent" },
  { name: "verify_agent", label: "Verify" },
  { name: "explain_agent", label: "Explain" },
];

const VI_DU = [
  "Tính đạo hàm của hàm số y = x^3 - 3x^2 + 2x tại điểm x = 1",
  "Một vật dao động điều hoà với biên độ 5 cm, tần số 2 Hz. Tính vận tốc cực đại.",
  "Đốt cháy hoàn toàn 5,6 gam Fe trong khí O2. Tính khối lượng Fe3O4 thu được.",
];

export default function App() {
  const [question, setQuestion] = useState("");
  const [running, setRunning] = useState(false);
  const [agents, setAgents] = useState<AgentState[]>([]);
  const [answer, setAnswer] = useState("");
  const [totalMs, setTotalMs] = useState<number | null>(null);
  const [withinSla, setWithinSla] = useState<boolean | null>(null);
  const [warning, setWarning] = useState("");
  const [sympyFixes, setSympyFixes] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [health, setHealth] = useState<Health | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const answerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchHealth().then(setHealth);
  }, []);

  // Cuộn theo chữ đang chảy về.
  useEffect(() => {
    answerRef.current?.scrollTo({ top: answerRef.current.scrollHeight });
  }, [answer]);

  function reset() {
    setAgents(
      ORDER.map((a) => ({ name: a.name, label: a.label, status: "waiting" as const })),
    );
    setAnswer("");
    setTotalMs(null);
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
          // Ba Subject Agent dùng chung một ô trên thanh tiến trình.
          const isSubject =
            ev.name !== "verify_agent" &&
            ev.name !== "explain_agent" &&
            ev.name.endsWith("_agent");
          const slot = isSubject ? "math_agent" : ev.name;
          const i = next.findIndex((a) => a.name === slot);
          if (i === -1) return prev;
          next[i] = {
            ...next[i],
            label: ev.label,
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
      case "cuu_dap_an":
        setWarning(
          `Không dựng được lời giải từng bước. Đáp án ${ev.gia_tri} do công cụ ` +
            `tính trực tiếp từ đề (${ev.cach_lam}). Hãy tự đối chiếu cách làm.`,
        );
        break;
      case "done":
        setTotalMs(ev.total_ms);
        setWithinSla(ev.within_sla);
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
      for await (const ev of solveStream(q, abortRef.current.signal)) {
        applyEvent(ev);
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        setError((err as Error).message);
      }
    } finally {
      setRunning(false);
    }
  }

  function onStop() {
    abortRef.current?.abort();
    setRunning(false);
  }

  return (
    <div className="app">
      <header>
        <h1>ViMultiAgent</h1>
        <p className="sub">Hệ thống đa tác tử giải bài tập STEM bằng tiếng Việt</p>
        {health && (
          <div className="health">
            <span>{health.model_heavy}</span>
            <span>SymPy {health.tools.sympy ? "✓" : "✕"}</span>
            <span>Đơn vị {health.tools.units ? "✓" : "✕"}</span>
          </div>
        )}
      </header>

      <form onSubmit={onSubmit}>
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Nhập câu hỏi Toán, Lý hoặc Hoá…"
          rows={4}
          disabled={running}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) onSubmit(e);
          }}
        />
        <div className="actions">
          <button type="submit" disabled={running || !question.trim()}>
            {running ? "Đang giải…" : "Giải bài"}
          </button>
          {running && (
            <button type="button" className="ghost" onClick={onStop}>
              Dừng
            </button>
          )}
          <span className="hint">Ctrl + Enter để gửi</span>
        </div>
      </form>

      {!running && !answer && (
        <div className="examples">
          <span>Thử nhanh:</span>
          {VI_DU.map((v, i) => (
            <button key={i} type="button" onClick={() => setQuestion(v)}>
              {["Toán", "Lý", "Hoá"][i]}
            </button>
          ))}
        </div>
      )}

      <AgentTimeline agents={agents} />

      {sympyFixes.length > 0 && (
        <div className="fixed">
          <strong>SymPy đã sửa {sympyFixes.length} bước tính sai:</strong>
          <ul>
            {sympyFixes.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </div>
      )}

      {warning && <div className="warn">{warning}</div>}
      {error && <div className="err">Lỗi: {error}</div>}

      {answer && (
        <div className="answer" ref={answerRef}>
          <Markdown text={answer} />
        </div>
      )}

      {totalMs !== null && (
        <div className={`sla ${withinSla ? "ok" : "over"}`}>
          Tổng thời gian {(totalMs / 1000).toFixed(1)}s —{" "}
          {withinSla ? "đạt" : "vượt"} mốc {health?.sla_seconds ?? 90} giây
        </div>
      )}
    </div>
  );
}
