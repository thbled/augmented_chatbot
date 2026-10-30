import axios from 'axios';

import type { ChatErrorCode, Locale, Role } from '../types/chat';
import { readSseStream } from './sse';

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  headers: { 'Content-Type': 'application/json' },
});

export interface ChatPayload {
  locale: Locale;
  messages: { role: Role; content: string }[];
}

export class ChatApiError extends Error {
  readonly code: ChatErrorCode;

  constructor(code: ChatErrorCode) {
    super(code);
    this.name = 'ChatApiError';
    this.code = code;
  }
}

const SERVER_ERROR_CODES: ChatErrorCode[] = ['llm_timeout', 'llm_unavailable', 'internal_error'];

export function errorFromStatus(status: number | undefined): ChatErrorCode {
  if (status === 429) return 'rate_limited';
  if (status === 413) return 'message_too_long';
  if (status === 400) return 'invalid_request';
  if (status && status >= 500) return 'llm_unavailable';
  return 'network';
}

export function isAbortError(error: unknown): boolean {
  return axios.isCancel(error) || (error instanceof DOMException && error.name === 'AbortError');
}

interface StreamOptions {
  signal?: AbortSignal;
  onDelta: (text: string) => void;
  /** Texte complet faisant foi, qui remplace tout ce qui a été reçu jusque-là. */
  onReplace?: (text: string) => void;
}

/**
 * Envoie la conversation à l'API et transmet la réponse au fil de l'eau.
 * Rejette avec `ChatApiError` en cas d'erreur, ou avec une erreur d'annulation si `signal`
 * est interrompu.
 */
export async function streamChat(
  payload: ChatPayload,
  { signal, onDelta, onReplace }: StreamOptions,
) {
  let stream: ReadableStream<Uint8Array>;
  try {
    const response = await apiClient.post<ReadableStream<Uint8Array>>('/chat', payload, {
      adapter: 'fetch',
      responseType: 'stream',
      headers: { Accept: 'text/event-stream' },
      signal,
    });
    stream = response.data;
  } catch (error) {
    if (isAbortError(error)) throw error;
    const status = axios.isAxiosError(error) ? error.response?.status : undefined;
    throw new ChatApiError(errorFromStatus(status));
  }

  let finished = false;
  await readSseStream(stream, (event) => {
    if (typeof event !== 'object' || event === null) return;
    const { type, text, code } = event as { type?: string; text?: unknown; code?: unknown };
    if (type === 'delta' && typeof text === 'string') {
      onDelta(text);
    } else if (type === 'replace' && typeof text === 'string') {
      onReplace?.(text);
    } else if (type === 'done') {
      finished = true;
    } else if (type === 'error') {
      const known = SERVER_ERROR_CODES.find((item) => item === code);
      throw new ChatApiError(known ?? 'internal_error');
    }
  });
  if (!finished) throw new ChatApiError('interrupted');
}
