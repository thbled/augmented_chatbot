export const EVENT_NAME = import.meta.env.VITE_EVENT_NAME || 'Conférence';

/** Doit rester cohérent avec MAX_USER_MESSAGE_CHARS côté backend. */
export const MAX_MESSAGE_LENGTH = 2000;

export const STORAGE_KEYS = {
  conversation: 'chat.conversation.v1',
  theme: 'theme',
  language: 'lang',
} as const;
