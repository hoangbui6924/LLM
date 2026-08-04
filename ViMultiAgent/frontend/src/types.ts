// Hợp đồng sự kiện giữa backend (SSE) và giao diện.
// Giữ khớp với `manager.solve_stream` bên Python.

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

/** Subject Agent hỏng, đáp án lấy từ bộ tính lại độc lập. */
export interface CuuDapAnEvent {
  type: "cuu_dap_an";
  gia_tri: string;
  cach_lam: string;
}

export interface DoneEvent {
  type: "done";
  total_ms: number;
  within_sla: boolean;
  warning?: string;
  result: unknown;
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
  | DoneEvent
  | ErrorEvent;

/** Trạng thái hiển thị của một agent trên thanh tiến trình. */
export interface AgentState {
  name: AgentName;
  label: string;
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
