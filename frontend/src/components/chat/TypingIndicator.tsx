import { useTranslation } from 'react-i18next';

export function TypingIndicator() {
  const { t } = useTranslation();
  return (
    <div className="flex h-8 items-center gap-1.5" role="presentation">
      {[0, 150, 300].map((delay) => (
        <span
          key={delay}
          aria-hidden="true"
          className="size-2 animate-bounce rounded-full bg-brand-400 dark:bg-brand-300"
          style={{ animationDelay: `${delay}ms` }}
        />
      ))}
      <span className="sr-only">{t('chat.thinking')}</span>
    </div>
  );
}
