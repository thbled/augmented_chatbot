import {
  Building2,
  CalendarClock,
  CircleHelp,
  MapPin,
  Route,
  Users,
  type LucideIcon,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { EVENT_NAME } from '../config';
import { useChatActions } from '../context/ChatActions';

const STARTERS: { key: string; icon: LucideIcon }[] = [
  { key: 'now', icon: CalendarClock },
  { key: 'speakers', icon: Users },
  { key: 'planning', icon: Route },
  { key: 'partners', icon: Building2 },
  { key: 'practical', icon: MapPin },
  { key: 'capabilities', icon: CircleHelp },
];

export function Welcome() {
  const { t } = useTranslation();
  const { ask, busy } = useChatActions();

  return (
    <section aria-labelledby="welcome-title" className="animate-fade-in py-4 sm:py-10">
      <div className="mb-8">
        <p className="mb-3 inline-flex items-center rounded-full bg-brand-100 px-3 py-1 text-xs font-semibold tracking-wide text-brand-800 uppercase dark:bg-brand-400/15 dark:text-brand-200">
          {t('app.subtitle')}
        </p>
        <h2
          id="welcome-title"
          className="text-2xl font-semibold tracking-tight text-balance text-slate-900 sm:text-3xl dark:text-white"
        >
          {t('welcome.title', { event: EVENT_NAME })}
        </h2>
        <p className="mt-3 max-w-prose leading-relaxed text-pretty text-slate-600 dark:text-slate-300">
          {t('welcome.intro')}
        </p>
      </div>

      <h3 className="mb-3 text-sm font-semibold text-slate-500 dark:text-slate-400">
        {t('welcome.starterHeading')}
      </h3>
      <ul className="grid gap-2.5 sm:grid-cols-2">
        {STARTERS.map(({ key, icon: Icon }) => {
          const question = t(`welcome.starters.${key}`);
          return (
            <li key={key}>
              <button
                type="button"
                disabled={busy}
                onClick={() => ask(question)}
                className="card flex min-h-14 w-full items-center gap-3 px-4 py-3 text-left font-medium text-slate-800 transition-colors hover:border-brand-300 hover:bg-brand-50/50 disabled:opacity-60 dark:text-slate-100 dark:hover:border-brand-400/40 dark:hover:bg-brand-400/10"
              >
                <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-700 dark:bg-brand-400/15 dark:text-brand-200">
                  <Icon aria-hidden="true" className="size-5" />
                </span>
                {question}
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
