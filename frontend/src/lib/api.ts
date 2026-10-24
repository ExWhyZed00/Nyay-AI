import type { ChatEvent, Conversation, ServerMessage } from "./types";

const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/+$/, "");

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export function errorMessage(e: unknown): string {
  if (e instanceof Error) {
    if (e.name === "TypeError") {
      return "Could not reach the server. Check your internet connection and that the backend is running.";
    }
    return e.message;
  }
  return "Something went wrong.";
}

async function readError(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail) && body.detail[0]?.msg) return String(body.detail[0].msg);
  } catch {
    /* ignore */
  }
  return `Request failed (${res.status}).`;
}

async function request<T>(path: string, token: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${token}`, ...(init?.headers ?? {}) },
  });
  if (!res.ok) throw new ApiError(res.status, await readError(res));
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const listConversations = (token: string) => request<Conversation[]>("/conversations", token);

export const getMessages = (token: string, id: string) =>
  request<ServerMessage[]>(`/conversations/${id}/messages`, token);

export const deleteConversation = (token: string, id: string) =>
  request<void>(`/conversations/${id}`, token, { method: "DELETE" });

/** Sends a question and calls onEvent for every streamed event (status, token, done ...). */
export async function streamChat(
  token: string,
  body: { message: string; conversation_id: string | null; language: string },
  onEvent: (event: ChatEvent) => void,
  signal: AbortSignal
): Promise<void> {
  const res = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok) throw new ApiError(res.status, await readError(res));
  if (!res.body) throw new Error("The server sent no data.");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      for (const line of block.split("\n")) {
        if (line.startsWith("data: ")) {
          try {
            onEvent(JSON.parse(line.slice(6)) as ChatEvent);
          } catch {
            /* ignore a malformed line */
          }
        }
      }
      boundary = buffer.indexOf("\n\n");
    }
  }
}
