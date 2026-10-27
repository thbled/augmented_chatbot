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
      <ul className="flex flex-wrap gap-2">
        {suggestions.map((suggestion) => (
          <li key={suggestion}>
            <button
              type="button"
              disabled={busy}
              onClick={() => ask(suggestion)}
              className="inline-flex min-h-11 items-center gap-2 rounded-2xl border border-brand-200 bg-white px-4 py-2 text-left text-sm font-medium text-brand-800 shadow-sm shadow-slate-900/5 transition-colors hover:border-brand-400 hover:bg-brand-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-brand-400/30 dark:bg-white/5 dark:text-brand-100 dark:shadow-none dark:hover:border-brand-300/60 dark:hover:bg-brand-400/10"
            >
              <CornerDownRight aria-hidden="true" className="size-4 shrink-0 opacity-70" />
              {frenchSpacing(suggestion)}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
