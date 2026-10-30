import { AlertCircle, RotateCcw, Sparkles } from 'lucide-react';
import { lazy, memo, Suspense, useMemo } from 'react';
import { useTranslation } from 'react-i18next';

import { parseAssistantMessage } from '../../lib/parseMessage';
import type { CardSegment, MessageSegment } from '../../types/cards';
import type { ChatMessage } from '../../types/chat';
import { CardSkeleton } from '../cards/CardSkeleton';
import { PartnerCard } from '../cards/PartnerCard';
import { SessionCard } from '../cards/SessionCard';
import { SpeakerCard } from '../cards/SpeakerCard';
import { SuggestionChips } from './SuggestionChips';
import { TypingIndicator } from './TypingIndicator';

// Le rendu Markdown (et ses dépendances) n'est chargé qu'à la première réponse :
// l'écran d'accueil s'affiche plus vite après le scan du QR code.
const Markdown = lazy(() => import('./Markdown'));

function PlainText({ text }: { text: string }) {
  return <p className="leading-relaxed whitespace-pre-wrap">{text}</p>;
}

type Group =
  | { kind: 'markdown'; text: string }
  | { kind: 'pending' }
  | { kind: 'cards'; cardKind: CardSegment['kind']; cards: CardSegment[] };

function groupSegments(segments: MessageSegment[]): Group[] {
  const groups: Group[] = [];
  for (const segment of segments) {
    if (segment.kind === 'markdown') {
      groups.push({ kind: 'markdown', text: segment.text });
    } else if (segment.kind === 'pending') {
      groups.push({ kind: 'pending' });
    } else {
      const last = groups.at(-1);
      if (last?.kind === 'cards' && last.cardKind === segment.kind) last.cards.push(segment);
      else groups.push({ kind: 'cards', cardKind: segment.kind, cards: [segment] });
    }
  }
  return groups;
}

function renderCard(card: CardSegment) {
  switch (card.kind) {
    case 'speaker':
      return <SpeakerCard speaker={card.data} />;
    case 'session':
      return <SessionCard session={card.data} />;
    case 'partner':
      return <PartnerCard partner={card.data} />;
  }
}

function CardGroup({ group }: { group: Extract<Group, { kind: 'cards' }> }) {
  const keyed = group.cards.map((card, index) => ({
    card,
    key: `${card.kind}-${card.data.id ?? index}`,
  }));

  if (group.cardKind === 'session' || keyed.length === 1) {
    return (
      <ul className="space-y-3">
        {keyed.map(({ card, key }) => (
          <li key={key}>{renderCard(card)}</li>
        ))}
      </ul>
    );
  }
  // Plusieurs speakers ou partenaires : carrousel horizontal sur mobile, grille au-delà.
  return (
    <ul className="scrollbar-none -mx-4 flex snap-x snap-mandatory gap-3 overflow-x-auto px-4 pb-1 sm:mx-0 sm:grid sm:grid-cols-2 sm:overflow-visible sm:px-0">
      {keyed.map(({ card, key }) => (
        <li key={key} className="w-[82%] shrink-0 snap-start sm:w-auto">
          {renderCard(card)}
        </li>
      ))}
    </ul>
  );
}

interface AssistantMessageProps {
  message: ChatMessage;
  isLast: boolean;
  onRetry: () => void;
}

export const AssistantMessage = memo(function AssistantMessage({
  message,
  isLast,
  onRetry,
}: AssistantMessageProps) {
  const { t } = useTranslation();
  const streaming = message.status === 'streaming';
  const parsed = useMemo(
    () => parseAssistantMessage(message.content, streaming),
    [message.content, streaming],
  );
  const groups = useMemo(() => groupSegments(parsed.segments), [parsed.segments]);

  return (
    <article className="flex animate-fade-in gap-3" aria-busy={streaming}>
      <span
        aria-hidden="true"
        className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-lg bg-brand-900 text-brand-100 dark:bg-brand-800"
      >
        <Sparkles className="size-3.5" strokeWidth={2} />
      </span>
      <div className="min-w-0 flex-1 space-y-3">
        <h2 className="sr-only">{t('chat.assistant')}</h2>
        {streaming && groups.length === 0 && <TypingIndicator />}
        {groups.map((group, index) => {
          if (group.kind === 'markdown') {
            return (
              <Suspense key={index} fallback={<PlainText text={group.text} />}>
                <Markdown text={group.text} />
              </Suspense>
            );
          }
          if (group.kind === 'pending') return <CardSkeleton key={index} />;
          return <CardGroup key={index} group={group} />;
        })}

        {message.status === 'stopped' && (
          <p className="text-sm text-slate-500 italic dark:text-slate-400">{t('chat.stopped')}</p>
        )}

        {message.status === 'error' && (
          <div
            role="alert"
            className="flex flex-col gap-2 rounded-2xl border border-red-200 bg-red-50 p-3 text-sm text-red-800 sm:flex-row sm:items-center dark:border-red-400/30 dark:bg-red-500/10 dark:text-red-200"
          >
            <p className="flex flex-1 items-start gap-2">
              <AlertCircle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
              {t(`errors.${message.errorCode ?? 'internal_error'}`)}
            </p>
            {isLast && message.errorCode !== 'rate_limited' && (
              <button
                type="button"
                onClick={onRetry}
                className="inline-flex min-h-11 items-center justify-center gap-1.5 self-start rounded-full bg-white px-4 font-semibold text-red-800 ring-1 ring-red-200 hover:bg-red-100 sm:self-auto dark:bg-transparent dark:text-red-100 dark:ring-red-400/40 dark:hover:bg-red-500/20"
              >
                <RotateCcw aria-hidden="true" className="size-4" />
                {t('chat.retry')}
              </button>
            )}
          </div>
        )}

        {isLast && message.status === 'done' && parsed.suggestions.length > 0 && (
          <SuggestionChips suggestions={parsed.suggestions} />
        )}
      </div>
    </article>
  );
});
