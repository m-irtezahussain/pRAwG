export type ChatRole = "user" | "assistant";

export type ChatHistoryMessage = {
  role: ChatRole;
  content: string;
};

export type ChatSource = {
  id: string;
  text: string;
  distance: number | null;
  metadata: Record<string, string | number | boolean>;
};

export type ChatResponse = {
  answer: string;
  sources: ChatSource[];
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

export async function askKnowledgeBase(
  question: string,
  history: ChatHistoryMessage[],
  signal?: AbortSignal,
): Promise<ChatResponse> {
  const response = await fetch(`${API_URL}/api/v1/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, history, top_k: 5 }),
    signal,
  });
  if (response.ok) return response.json() as Promise<ChatResponse>;

  let message = "We couldn't get an answer from your knowledge base. Please try again.";
  try {
    const payload = await response.json() as { detail?: string | { msg?: string }[] };
    if (typeof payload.detail === "string") message = payload.detail;
    else if (Array.isArray(payload.detail)) message = payload.detail[0]?.msg ?? message;
  } catch {
    // Retain the safe fallback for non-JSON proxy responses.
  }
  throw new Error(message);
}
