import { useTranslation } from 'react-i18next';

import { useChatActions } from '../context/ChatActions';

/** Accès permanent à la session en cours : sujet, intervenants, points clés, questions à poser. */
export function LiveSessionButton() {
  const { t } = useTranslation();
  const { ask, busy } = useChatActions();

  return (
    <div className="mx-auto mb-2.5 flex w-full max-w-2xl justify-center">
      <button
        type="button"
        disabled={busy}
        onClick={() => ask(t('live.question'))}
        className="inline-flex h-8 items-center gap-2 rounded-full bg-white px-3.5 text-[0.8rem] font-medium text-slate-700 shadow-[0_1px_2px_rgb(0_0_0/0.04)] ring-1 ring-black/6 transition hover:text-brand-800 hover:ring-brand-300 disabled:opacity-50 dark:bg-white/5 dark:text-slate-200 dark:ring-white/10 dark:hover:ring-brand-400/50"
      >
        <span aria-hidden="true" className="relative flex size-2">
          <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-500/60 motion-reduce:hidden" />
          <span className="relative inline-flex size-2 rounded-full bg-emerald-500" />
        </span>
        {t('live.label')}
      </button>
    </div>
  );
}
