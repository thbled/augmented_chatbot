import {
  CalendarDays,
  ChevronRight,
  Coffee,
  Sparkles,
  Users,
  type LucideIcon,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { useChatActions } from '../context/ChatActions';

/** Accès rapides de l'accueil : les questions pratiques les plus fréquentes. */
const QUICK: { key: string; icon: LucideIcon }[] = [
  { key: 'now', icon: Sparkles },
  { key: 'speakers', icon: Users },
  { key: 'planning', icon: CalendarDays },
  { key: 'break', icon: Coffee },
];

export function QuickActions() {
  const { t } = useTranslation();
  const { ask, busy } = useChatActions();

  return (
    <nav aria-label={t('quick.label')}>
      <ul className="divide-y divide-black/5 overflow-hidden rounded-2xl bg-white ring-1 ring-black/5 dark:divide-white/6 dark:bg-white/3 dark:ring-white/7">
        {QUICK.map(({ key, icon: Icon }) => (
          <li key={key}>
            <button
              type="button"
              disabled={busy}
              onClick={() => ask(t(`quick.${key}.question`))}
              className="group flex w-full items-center gap-3.5 px-4 py-3.5 text-left transition-colors hover:bg-brand-50/60 disabled:opacity-60 dark:hover:bg-white/4"
            >
              <Icon
                aria-hidden="true"
                strokeWidth={1.75}
                className="size-[1.15rem] shrink-0 text-brand-700 dark:text-brand-300"
              />
              <span className="min-w-0 flex-1">
                <span className="block text-[0.92rem] font-medium text-slate-900 dark:text-white">
                  {t(`quick.${key}.label`)}
                </span>
                <span className="block text-[0.8rem] text-slate-500 dark:text-slate-400">
                  {t(`quick.${key}.hint`)}
                </span>
              </span>
              <ChevronRight
                aria-hidden="true"
                className="size-4 shrink-0 text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-brand-600 dark:text-slate-600"
              />
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}
