export interface ChatMessage {
  message_id: string;
  user_id: string;
  timestamp: string;
  question: string;
  answer: string;
  sources?: string[];
  search_performed: boolean;
  isUserMessage?: boolean; // A frontend-only flag to differentiate UI
}

export interface QueryResponse {
  message_id: string;
  answer: string;
  sources?: string[];
  search_performed: boolean;
}