import { CornerDownRight } from 'lucide-react';
import { useId } from 'react';
import { useTranslation } from 'react-i18next';

import { useChatActions } from '../../context/ChatActions';
import { frenchSpacing } from '../../lib/format';

interface SuggestionChipsProps {
  suggestions: string[];
  /** Titre visible (accueil) ; sinon le titre n'est destiné qu'aux lecteurs d'écran. */
  heading?: string;
}

export function SuggestionChips({ suggestions, heading }: SuggestionChipsProps) {
  const { t } = useTranslation();
  const { ask, busy } = useChatActions();
  const headingId = useId();

  return (
    <section aria-labelledby={headingId} className="pt-1">
      <h3
        id={headingId}
        className={
          heading ? 'mb-3 text-sm font-semibold text-slate-500 dark:text-slate-400' : 'sr-only'
        }
      >
        {heading ?? t('chat.suggestionsLabel')}
      </h3>
      <ul className="flex flex-col items-start gap-1.5">
        {suggestions.map((suggestion) => (
          <li key={suggestion}>
            <button
              type="button"
              disabled={busy}
              onClick={() => ask(suggestion)}
              className="group inline-flex min-h-10 items-center gap-2 rounded-xl px-3 py-2 text-left text-[0.88rem] text-slate-700 ring-1 ring-black/8 transition hover:bg-white hover:text-brand-800 hover:ring-brand-300 disabled:cursor-not-allowed disabled:opacity-60 dark:text-slate-200 dark:ring-white/10 dark:hover:bg-white/5 dark:hover:text-brand-100"
            >
              <CornerDownRight
                aria-hidden="true"
                className="size-3.5 shrink-0 text-slate-400 group-hover:text-brand-600"
              />
              {frenchSpacing(suggestion)}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
