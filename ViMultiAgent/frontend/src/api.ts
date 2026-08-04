// Đọc SSE bằng `fetch` chứ không dùng `EventSource`.
//
// Lý do: EventSource chỉ gửi được GET, mà đề bài có thể dài vài nghìn ký tự nên
// phải đi bằng POST body. Đổi lại ta tự tách khung sự kiện — phần đó nằm gọn
// trong `parseSSE` bên dưới.

import type { HistoryRow, StreamEvent } from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "/api";

export async function* solveStream(
  question: string,
  signal?: AbortSignal,
): AsyncGenerator<StreamEvent> {
  const res = await fetch(`${BASE}/solve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
    signal,
  });

  if (!res.ok || !res.body) {
    throw new Error(`Backend trả lỗi ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // Mỗi khung SSE kết thúc bằng một dòng trống. Chuẩn SSE cho phép cả "\n" lẫn
    // "\r\n" làm ký tự xuống dòng, và `sse-starlette` bên backend dùng "\r\n" —
    // tức khung kết thúc bằng "\r\n\r\n", KHÔNG chứa hai ký tự "\n" liền nhau.
    // Chỉ tìm "\n\n" thì không bao giờ thấy ranh giới khung và giao diện đứng im
    // vĩnh viễn. Đã mất một buổi vì đúng chỗ này, do chỉ thử bằng curl.
    for (;;) {
      const sep = timKhungKetThuc(buffer);
      if (!sep) break;
      const ev = parseSSE(buffer.slice(0, sep.dau));
      buffer = buffer.slice(sep.cuoi);
      if (ev) yield ev;
    }
  }
}

/** Tìm dòng trống kết thúc khung, chấp nhận cả "\n\n" lẫn "\r\n\r\n". */
function timKhungKetThuc(buf: string): { dau: number; cuoi: number } | null {
  const crlf = buf.indexOf("\r\n\r\n");
  const lf = buf.indexOf("\n\n");
  if (crlf === -1 && lf === -1) return null;
  // Lấy ranh giới xuất hiện TRƯỚC, để không nuốt nhầm sang khung kế tiếp.
  if (crlf !== -1 && (lf === -1 || crlf < lf)) {
    return { dau: crlf, cuoi: crlf + 4 };
  }
  return { dau: lf, cuoi: lf + 2 };
}

function parseSSE(frame: string): StreamEvent | null {
  const dataLines = frame
    .split(/\r?\n/)
    .filter((l) => l.startsWith("data:"))
    .map((l) => l.slice(5).trim());
  if (dataLines.length === 0) return null;
  try {
    return JSON.parse(dataLines.join("\n")) as StreamEvent;
  } catch {
    return null;
  }
}

export async function fetchHistory(limit = 20): Promise<HistoryRow[]> {
  const res = await fetch(`${BASE}/history?limit=${limit}`);
  if (!res.ok) return [];
  return res.json();
}

export interface Health {
  status: string;
  model_heavy: string;
  model_light: string;
  sla_seconds: number;
  tools: Record<string, boolean>;
}

export async function fetchHealth(): Promise<Health | null> {
  try {
    const res = await fetch(`${BASE}/health`);
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}
