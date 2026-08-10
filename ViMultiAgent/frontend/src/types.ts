// Hợp đồng sự kiện giữa backend (SSE) và giao diện.
// Giữ khớp với `manager.solve_stream` và `core/schemas.py` bên Python.

export type AgentName =
  | "planner"
  | "router"
  | "math_agent"
  | "physics_agent"
  | "chemistry_agent"
  | "verify_agent"
  | "explain_agent";

export type Verdict = "PASS" | "FAIL" | "UNCERTAIN";

export interface AgentEvent {
  type: "agent";
  name: AgentName;
  label: string;
  status: "start" | "done";
  ok?: boolean;
  ms?: number;
  detail?: string;
  verdict?: Verdict;
  retry?: boolean;
  sympy_fixed?: number;
}

export interface TokenEvent {
  type: "token";
  text: string;
}

export interface RetryEvent {
  type: "retry";
  round: number;
  reason: string;
}

/** SymPy đã ghi đè con số model tự nhẩm. */
export interface ArbiterEvent {
  type: "arbiter";
  count: number;
  items: string[];
}

/** Đáp án lấy từ bộ tính lại độc lập vì lời giải không qua kiểm chứng. */
export interface CuuDapAnEvent {
  type: "cuu_dap_an";
  gia_tri: string;
  cach_lam: string;
}

/**
 * Đáp án đã chốt, phát TRƯỚC khi Explain Agent chạy.
 *
 * Đáp số xong hẳn từ lúc này — Explain chỉ diễn đạt lại và không được đổi nó.
 * Trước đây giao diện phải chờ sự kiện `done` (sau khi giảng xong) mới hiện được
 * đáp án, tức bắt người dùng chờ thêm ~10 giây để đọc một con số đã có sẵn.
 */
export interface DapAnEvent {
  type: "dap_an";
  gia_tri: string;
  latex: string;
  mcq: string | null;
  verdict: Verdict | "";
  confidence: number;
  warning: string;
}

// ---------------------------------------------------------------------------
// Kết quả đầy đủ, gửi kèm sự kiện `done`
// ---------------------------------------------------------------------------

export interface Quantity {
  symbol: string;
  value: number | null;
  unit: string | null;
  description_vi: string;
}

export interface SolutionStep {
  id: number;
  goal_vi: string;
  expression: string;
  result: string;
  reason_vi: string;
}

export interface SolveResult {
  question: string;
  plan: {
    subject: string;
    topic: string;
    question_type: string;
    givens: Quantity[];
    unknowns: Quantity[];
    normalized_question: string;
    confidence: number;
  } | null;
  route: {
    subject: string;
    agent_name: string;
    reason_vi: string;
    confidence: number;
    decided_by: "phobert" | "rule" | "llm";
    phobert_confidence: number | null;
  } | null;
  solution: {
    steps: SolutionStep[];
    final_answer: string;
    final_answer_latex: string;
    unit: string | null;
    confidence: number;
  } | null;
  verify: {
    verdict: Verdict;
    checks: { kind: string; passed: boolean; detail_vi: string }[];
    confidence: number;
  } | null;
  trace: {
    spans: { agent: string; duration_ms: number; ok: boolean }[];
    retry_rounds: number;
  };
  warning_vi: string;
}

export interface DoneEvent {
  type: "done";
  total_ms: number;
  within_sla: boolean;
  warning?: string;
  result: SolveResult;
}

export interface ErrorEvent {
  type: "error";
  message: string;
}

export type StreamEvent =
  | AgentEvent
  | TokenEvent
  | RetryEvent
  | ArbiterEvent
  | CuuDapAnEvent
  | DapAnEvent
  | DoneEvent
  | ErrorEvent;

/** Trạng thái hiển thị của một agent trên thanh tiến trình. */
export interface AgentState {
  name: AgentName;
  label: string;
  mo_ta: string;
  status: "waiting" | "running" | "done" | "failed";
  ms?: number;
  detail?: string;
  verdict?: Verdict;
  retry?: boolean;
}

export interface HistoryRow {
  id: number;
  question: string;
  answer: string;
  subject: string;
  verdict: string;
  duration_ms: number;
  created_at: string;
}

/** Bài tập cùng dạng sinh sau khi giải xong.
 *
 * `dap_an` do Python tính từ tham số của chính đề bài (mẫu tham số hoá trong
 * `eval/`), không do model sinh — nên không cần trường verdict như bài chính.
 */
export interface BaiTuongTuData {
  de_bai: string;
  dap_an: string;
  don_vi: string;
  topic: string;
  muc_do: string;
  goi_y: string;
  nguon: string;
}
