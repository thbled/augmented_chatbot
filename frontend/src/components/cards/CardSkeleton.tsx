import { useTranslation } from 'react-i18next';

export function CardSkeleton() {
  const { t } = useTranslation();
  return (
    <div className="card flex animate-pulse items-center gap-3 p-4" role="presentation">
      <span className="size-12 rounded-full bg-slate-200 dark:bg-white/10" />
      <span className="flex-1 space-y-2">
        <span className="block h-3.5 w-2/3 rounded bg-slate-200 dark:bg-white/10" />
        <span className="block h-3 w-1/2 rounded bg-slate-200 dark:bg-white/10" />
      </span>
      <span className="sr-only">{t('chat.loadingCard')}</span>
    </div>
  );
}
