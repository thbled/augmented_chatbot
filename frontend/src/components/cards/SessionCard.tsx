import { CalendarClock, ChevronRight, MapPin } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { useChatActions } from '../../context/ChatActions';
import { formatDay, formatTimeRange } from '../../lib/format';
import type { SessionCardData } from '../../types/cards';
import type { Locale } from '../../types/chat';
import { Avatar } from '../common/Avatar';

export function SessionCard({ session }: { session: SessionCardData }) {
  const { t, i18n } = useTranslation();
  const { ask, busy } = useChatActions();
  const locale: Locale = i18n.resolvedLanguage === 'en' ? 'en' : 'fr';
  const when = [formatDay(session.date, locale), formatTimeRange(session.start, session.end)]
    .filter(Boolean)
    .join(' · ');

  return (
    <article className="card relative flex flex-col gap-2 overflow-hidden p-4 pl-5">
      <span
        aria-hidden="true"
        className="absolute inset-y-0 left-0 w-1 bg-brand-600 dark:bg-brand-400"
      />
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm font-medium text-brand-800 dark:text-brand-200">
        {when && (
          <span className="inline-flex items-center gap-1">
            <CalendarClock aria-hidden="true" className="size-4" />
            {when}
          </span>
        )}
        {session.room && (
          <span className="inline-flex items-center gap-1 text-slate-600 dark:text-slate-300">
            <MapPin aria-hidden="true" className="size-4" />
            {session.room}
          </span>
        )}
      </div>

      <h3 className="text-base leading-snug font-semibold text-slate-900 dark:text-white">
        {session.title}
      </h3>

      {(session.format || session.track || session.language) && (
        <ul className="flex flex-wrap gap-1.5">
          {[session.format, session.track, session.language].filter(Boolean).map((item) => (
            <li key={item} className="tag">
              {item}
            </li>
          ))}
        </ul>
      )}

      {session.summary && (
        <p className="line-clamp-3 text-sm leading-relaxed text-slate-600 dark:text-slate-300">
          {session.summary}
        </p>
      )}

      {session.speakers && (
        <div className="mt-1">
          <h4 className="sr-only">{t('cards.speakers')}</h4>
          <ul className="flex flex-wrap gap-2">
            {session.speakers.map((speaker) => (
              <li key={speaker.id ?? speaker.name}>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => ask(t('cards.questions.speaker', { name: speaker.name }))}
                  aria-label={t('cards.askSpeaker', { name: speaker.name })}
                  className="-ml-1 flex items-center gap-2 rounded-full py-0.5 pr-2.5 pl-1 transition-colors hover:bg-brand-50 disabled:opacity-60 dark:hover:bg-brand-400/10"
                >
                  <Avatar
                    name={speaker.name}
                    src={speaker.photoUrl}
                    className="size-7 text-[0.65rem]"
                  />
                  <span className="text-sm font-medium text-slate-800 underline decoration-slate-300 underline-offset-2 dark:text-slate-100 dark:decoration-slate-600">
                    {speaker.name}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div>
        <button
          type="button"
          className="link-button -ml-3"
          disabled={busy}
          onClick={() => ask(t('cards.questions.session', { title: session.title }))}
          aria-label={t('cards.askAboutItem', { name: session.title })}
        >
          {t('cards.askAbout')}
          <ChevronRight aria-hidden="true" className="size-4" />
        </button>
      </div>
    </article>
  );
}
