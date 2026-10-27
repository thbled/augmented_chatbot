import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';

import { HISTORY_SENT, MAX_MESSAGE_LENGTH, STORAGE_KEYS } from '../config';
import { ChatApiError, isAbortError, streamChat } from '../lib/api';
import { readJson, remove, writeJson } from '../lib/storage';
import type { ChatMessage, Locale } from '../types/chat';

let counter = 0;
const newId = () => `${Date.now().toString(36)}-${(counter++).toString(36)}`;

function restoreConversation(): ChatMessage[] {
  const stored = readJson<unknown>(STORAGE_KEYS.conversation, []);
  if (!Array.isArray(stored)) return [];
  return stored
    .filter((item): item is ChatMessage => {
      const m = item as Partial<ChatMessage> | null;
      return (
        typeof m?.id === 'string' &&
        (m.role === 'user' || m.role === 'assistant') &&
        typeof m.content === 'string'
      );
    })
    .map((m) => (m.status === 'streaming' ? { ...m, status: 'stopped' as const } : m));
}

/** Historique transmis au LLM : messages aboutis uniquement, dans la limite configurée. */
export function toHistory(messages: ChatMessage[]) {
  return messages
    .filter((m) => m.content.trim() && (m.role === 'user' || m.status !== 'error'))
    .slice(-HISTORY_SENT)
    .map(({ role, content }) => ({ role, content }));
}

export function useChat(locale: Locale) {
  const [messages, setMessages] = useState<ChatMessage[]>(restoreConversation);
  const controllerRef = useRef<AbortController | null>(null);
  const isStreaming = messages.some((m) => m.status === 'streaming');
  // Les actions lisent l'état courant via des refs pour rester stables entre deux rendus.
  const messagesRef = useRef(messages);
  useLayoutEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  useEffect(() => {
    // On ne persiste pas à chaque fragment reçu, seulement une fois la réponse terminée.
    if (isStreaming) return;
    if (messages.length) writeJson(STORAGE_KEYS.conversation, messages);
    else remove(STORAGE_KEYS.conversation);
  }, [messages, isStreaming]);

  useEffect(() => () => controllerRef.current?.abort(), []);

  const updateMessage = useCallback((id: string, update: (m: ChatMessage) => ChatMessage) => {
    setMessages((current) => current.map((m) => (m.id === id ? update(m) : m)));
  }, []);

  const run = useCallback(
    async (history: ChatMessage[]) => {
      const assistantId = newId();
      const controller = new AbortController();
      controllerRef.current = controller;
      setMessages([
        ...history,
        { id: assistantId, role: 'assistant', content: '', status: 'streaming' },
      ]);

      try {
        await streamChat(
          { locale, messages: toHistory(history) },
          {
            signal: controller.signal,
            onDelta: (text) =>
              updateMessage(assistantId, (m) => ({ ...m, content: m.content + text })),
          },
        );
        updateMessage(assistantId, (m) => ({ ...m, status: 'done' }));
      } catch (error) {
        if (controller.signal.aborted || isAbortError(error)) {
          updateMessage(assistantId, (m) => ({ ...m, status: 'stopped' }));
        } else {
          const errorCode = error instanceof ChatApiError ? error.code : 'network';
          updateMessage(assistantId, (m) => ({ ...m, status: 'error', errorCode }));
        }
      } finally {
        if (controllerRef.current === controller) controllerRef.current = null;
      }
    },
    [locale, updateMessage],
  );

  const send = useCallback(
    (text: string) => {
      const content = text.trim().slice(0, MAX_MESSAGE_LENGTH);
      if (!content || controllerRef.current) return;
      void run([...messagesRef.current, { id: newId(), role: 'user', content, status: 'done' }]);
    },
    [run],
  );

  const retry = useCallback(() => {
    if (controllerRef.current) return;
    const current = messagesRef.current;
    const history = current.at(-1)?.role === 'assistant' ? current.slice(0, -1) : current;
    if (history.at(-1)?.role === 'user') void run(history);
  }, [run]);

  const stop = useCallback(() => controllerRef.current?.abort(), []);

  const reset = useCallback(() => {
    controllerRef.current?.abort();
    controllerRef.current = null;
    setMessages([]);
  }, []);

  return { messages, isStreaming, send, retry, stop, reset };
}
