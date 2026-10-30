import { ArrowRight } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { EVENT_NAME } from '../config';
import { useChatActions } from '../context/ChatActions';
import { QuickActions } from './QuickActions';

/** Accueil sobre : salutation, résumé de l'événement mis en avant, accès pratiques. */
export function Welcome() {
  const { t } = useTranslation();
  const { ask, busy } = useChatActions();

  return (
    <section
      aria-labelledby="welcome-title"
      className="flex min-h-[calc(100dvh-14rem)] animate-fade-in flex-col pt-10 sm:pt-16"
    >
      <h2
        id="welcome-title"
        className="text-[1.65rem] leading-tight font-semibold tracking-tight text-balance text-slate-900 sm:text-[2rem] dark:text-white"
      >
        {t('welcome.title')}
      </h2>
      <p className="mt-2.5 max-w-md text-[0.95rem] leading-relaxed text-pretty text-slate-500 dark:text-slate-400">
        {t('welcome.intro', { event: EVENT_NAME })}
      </p>

      <div className="mt-auto space-y-3 pt-12">
        <button
          type="button"
          disabled={busy}
          onClick={() => ask(t('welcome.event.question'))}
          className="group relative w-full overflow-hidden rounded-2xl bg-brand-900 p-5 text-left text-white shadow-[0_8px_24px_-12px_rgb(20_50_40/0.5)] transition hover:bg-brand-800 disabled:opacity-60 dark:bg-brand-800 dark:hover:bg-brand-700"
        >
          <span
            aria-hidden="true"
            className="pointer-events-none absolute -top-10 -right-10 size-36 rounded-full bg-brand-400/20 blur-2xl"
          />
          <span className="relative inline-flex items-center gap-2 text-[0.7rem] font-medium tracking-[0.12em] text-brand-200 uppercase">
            <span aria-hidden="true" className="relative flex size-2">
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400/70 motion-reduce:hidden" />
              <span className="relative inline-flex size-2 rounded-full bg-emerald-400" />
            </span>
            {t('welcome.event.label')}
          </span>
          <span className="relative mt-2 flex items-center justify-between gap-3">
            <span>
              <span className="block text-[1.05rem] font-semibold">{t('welcome.event.title')}</span>
              <span className="mt-0.5 block text-[0.83rem] text-brand-100/80">
                {t('welcome.event.hint')}
              </span>
            </span>
            <span className="grid size-9 shrink-0 place-items-center rounded-full bg-white/10 transition group-hover:bg-white/20">
              <ArrowRight aria-hidden="true" className="size-4" />
            </span>
          </span>
        </button>

        <QuickActions />
      </div>
    </section>
  );
}
