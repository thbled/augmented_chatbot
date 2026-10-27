export type Role = 'user' | 'assistant';

export type MessageStatus = 'done' | 'streaming' | 'stopped' | 'error';

export type ChatErrorCode =
  | 'rate_limited'
  | 'message_too_long'
  | 'invalid_request'
  | 'llm_timeout'
  | 'llm_unavailable'
  | 'internal_error'
  | 'interrupted'
  | 'network';

export interface ChatMessage {
  id: string;
  role: Role;
  content: string;
  status: MessageStatus;
  errorCode?: ChatErrorCode;
}

export type Locale = 'fr' | 'en';
