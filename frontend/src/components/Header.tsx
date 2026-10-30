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
    <header className="sticky top-0 z-20 bg-canvas/85 pt-[env(safe-area-inset-top)] backdrop-blur-xl dark:bg-canvas-dark/85">
      <div className="mx-auto flex h-16 max-w-2xl items-center gap-3 px-4">
        <img src="/favicon.svg" alt="" className="size-8 rounded-[0.6rem]" />
        <div className="min-w-0 flex-1 leading-tight">
          <h1 className="truncate text-[0.92rem] font-semibold tracking-tight text-slate-900 dark:text-white">
            {EVENT_NAME}
          </h1>
          <p className="truncate text-xs text-slate-500 dark:text-slate-400">
            {t('app.subtitle')}
          </p>
        </div>

        <nav className="-mr-2 flex items-center" aria-label={t('header.actions')}>
          <button
            type="button"
            className="icon-button"
            onClick={onNewConversation}
            disabled={!canReset}
            aria-label={t('header.newConversation')}
            title={t('header.newConversation')}
          >
            <SquarePen aria-hidden="true" className="size-[1.15rem]" />
          </button>
          <button
            type="button"
            className="icon-button text-xs font-semibold tracking-wider"
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
              <Sun aria-hidden="true" className="size-[1.15rem]" />
            ) : (
              <Moon aria-hidden="true" className="size-[1.15rem]" />
            )}
          </button>
        </nav>
      </div>
      <div className="mx-auto h-px max-w-2xl bg-black/[0.06] dark:bg-white/[0.07]" />
    </header>
  );
}
