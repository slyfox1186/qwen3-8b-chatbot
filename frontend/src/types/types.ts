export interface ChatMessage {
  id?: string; // Added for identifying messages for updates
  role: "user" | "assistant" | "system";
  content: string;
  thinking?: string; // Added for storing the thinking section separately
  isInThinkBlock?: boolean; // Indicates if the assistant is currently in a thinking block
  isThinkingMessage?: boolean; // True if this message bubble is specifically for 'thinking' content
}

export interface ChatRequest {
  conv_id?: string;
  message: string;
}

export interface ChatResponse {
  role: "assistant";
  content: string;
}

export interface ConversationResponse {
  conv_id: string;
}

export interface HealthResponse {
  status: string;
  model: string;
}