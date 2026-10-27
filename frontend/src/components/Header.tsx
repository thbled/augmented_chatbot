import { Moon, SquarePen, Sun } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { EVENT_NAME } from '../config';
import type { Theme } from '../hooks/useTheme';

interface HeaderProps {
  theme: Theme;
  onToggleTheme: () => void;
  onNewConversation: () => void;
  canReset: boolean;
}

export function Header({ theme, onToggleTheme, onNewConversation, canReset }: HeaderProps) {
  const { t, i18n } = useTranslation();
  const nextLanguage = i18n.resolvedLanguage === 'en' ? 'fr' : 'en';

  return (
    <header className="sticky top-0 z-20 border-b border-slate-200/80 bg-slate-50/95 pt-[env(safe-area-inset-top)] backdrop-blur-md dark:border-white/10 dark:bg-[#0b1020]/95">
      <div className="mx-auto flex h-14 max-w-3xl items-center gap-2 px-3 sm:px-4">
        <img src="/favicon.svg" alt="" className="size-8 rounded-lg" />
        <div className="min-w-0 flex-1 leading-tight">
          <h1 className="truncate text-[0.95rem] font-semibold text-slate-900 dark:text-white">
            {EVENT_NAME}
          </h1>
          <p className="truncate text-xs text-slate-500 dark:text-slate-400">{t('app.subtitle')}</p>
        </div>

        <div className="flex items-center">
          <button
            type="button"
            className="icon-button"
            onClick={onNewConversation}
            disabled={!canReset}
            aria-label={t('header.newConversation')}
            title={t('header.newConversation')}
          >
            <SquarePen aria-hidden="true" className="size-5" />
          </button>
          <button
            type="button"
            className="icon-button text-sm font-semibold"
            onClick={() => void i18n.changeLanguage(nextLanguage)}
            aria-label={t('header.switchLanguage')}
            title={t('header.switchLanguage')}
            lang={nextLanguage}
          >
            <span aria-hidden="true">{t('header.languageShort')}</span>
          </button>
          <button
            type="button"
            className="icon-button"
            onClick={onToggleTheme}
            aria-label={theme === 'dark' ? t('header.themeToLight') : t('header.themeToDark')}
            title={theme === 'dark' ? t('header.themeToLight') : t('header.themeToDark')}
          >
            {theme === 'dark' ? (
              <Sun aria-hidden="true" className="size-5" />
            ) : (
              <Moon aria-hidden="true" className="size-5" />
            )}
          </button>
        </div>
      </div>
    </header>
  );
}
