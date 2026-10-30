import { ShieldCheck } from 'lucide-react';
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { SpeakerDialog } from './components/cards/SpeakerDialog';
import { MessageList } from './components/chat/MessageList';
import { Composer } from './components/Composer';
import { Header } from './components/Header';
import { LiveSessionButton } from './components/LiveSessionButton';
import { Welcome } from './components/Welcome';
import { ChatActionsContext, type ChatActions } from './context/ChatActions';
import { useChat } from './hooks/useChat';
import { useTheme } from './hooks/useTheme';
import { parseAssistantMessage, toPlainText } from './lib/parseMessage';
import type { SpeakerCardData } from './types/cards';
import type { Locale } from './types/chat';

/** Distance (px) au bas de page en deçà de laquelle on suit automatiquement la réponse. */
const STICKY_THRESHOLD = 160;

function scrollingElement(): HTMLElement {
  return (document.scrollingElement as HTMLElement | null) ?? document.documentElement;
}

export default function App() {
  const { t, i18n } = useTranslation();
  const locale: Locale = i18n.resolvedLanguage === 'en' ? 'en' : 'fr';
  const { theme, toggle } = useTheme();
  const { messages, isStreaming, send, retry, stop, reset } = useChat(locale);
  const [speaker, setSpeaker] = useState<SpeakerCardData | null>(null);
  const [announcement, setAnnouncement] = useState('');
  const composerRef = useRef<HTMLTextAreaElement | null>(null);
  const followRef = useRef(true);

  const actions = useMemo<ChatActions>(
    () => ({ ask: send, openSpeaker: setSpeaker, busy: isStreaming }),
    [send, isStreaming],
  );

  // Suivi automatique de la réponse tant que l'utilisateur est en bas de la conversation.
  useEffect(() => {
    const onScroll = () => {
      const el = scrollingElement();
      followRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < STICKY_THRESHOLD;
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const lastUserId = messages.findLast((m) => m.role === 'user')?.id;
  useLayoutEffect(() => {
    // Nouvelle question : on revient en bas quoi qu'il arrive.
    followRef.current = true;
  }, [lastUserId]);

  useLayoutEffect(() => {
    if (!followRef.current || messages.length === 0) return;
    const el = scrollingElement();
    el.scrollTo?.({ top: el.scrollHeight, behavior: 'auto' });
  }, [messages]);

  // Annonces pour les lecteurs d'écran : début puis contenu de la réponse.
  const last = messages.at(-1);
  const lastStatus = last?.role === 'assistant' ? last.status : undefined;
  useEffect(() => {
    if (!last || last.role !== 'assistant') return;
    if (lastStatus === 'streaming') {
      setAnnouncement(t('a11y.generating'));
    } else if (lastStatus === 'done') {
      setAnnouncement(
        t('a11y.answerReady', { text: toPlainText(parseAssistantMessage(last.content)) }),
      );
    }
    // L'annonce ne dépend que du changement de statut du dernier message.
    // eslint-disable-next-line react/exhaustive-deps
  }, [last?.id, lastStatus]);

  const onNewConversation = useCallback(() => {
    reset();
    setSpeaker(null);
    setAnnouncement(t('a11y.conversationReset'));
    composerRef.current?.focus();
  }, [reset, t]);

  return (
    <ChatActionsContext.Provider value={actions}>
      <div className="flex min-h-dvh flex-col">
        <a href="#composer" className="skip-link">
          {t('app.skipToComposer')}
        </a>
        <Header
          theme={theme}
          onToggleTheme={toggle}
          onNewConversation={onNewConversation}
          canReset={messages.length > 0}
        />

        <main
          id="conversation"
          aria-label={t('chat.conversationLabel')}
          className="mx-auto w-full max-w-2xl flex-1 px-4 pt-4 pb-6"
        >
          {messages.length === 0 ? (
            <Welcome />
          ) : (
            <MessageList messages={messages} onRetry={retry} />
          )}
        </main>

        <footer className="pb-safe sticky bottom-0 z-10 bg-gradient-to-t from-canvas from-80% to-canvas/0 px-4 pt-6 dark:from-canvas-dark dark:to-canvas-dark/0">
          {messages.length > 0 && <LiveSessionButton />}
          <Composer inputRef={composerRef} busy={isStreaming} onSend={send} onStop={stop} />
          <details className="group mx-auto mt-2 max-w-2xl text-center text-[0.7rem] text-slate-400 dark:text-slate-500">
            <summary className="inline-flex cursor-pointer list-none items-center gap-1.5 rounded-full px-2 py-1 transition-colors hover:text-slate-600 dark:hover:text-slate-300 [&::-webkit-details-marker]:hidden">
              <ShieldCheck aria-hidden="true" className="size-3" />
              {t('app.scope')}
            </summary>
            <p className="mx-auto mt-1 max-w-sm leading-relaxed text-slate-500 dark:text-slate-400">
              {t('app.disclaimer')}
            </p>
          </details>
        </footer>

        <output className="sr-only" aria-live="polite" aria-atomic="true">
          {announcement}
        </output>
        <SpeakerDialog speaker={speaker} onClose={() => setSpeaker(null)} />
      </div>
    </ChatActionsContext.Provider>
  );
}
