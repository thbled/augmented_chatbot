import { memo } from 'react';
import { useTranslation } from 'react-i18next';

export const UserMessage = memo(function UserMessage({ content }: { content: string }) {
  const { t } = useTranslation();
  return (
    <article className="flex animate-fade-in justify-end">
      <h2 className="sr-only">{t('chat.you')}</h2>
      <p className="max-w-[85%] rounded-[1.25rem] rounded-br-md bg-brand-100/70 px-4 py-2.5 text-[0.95rem] leading-relaxed break-words whitespace-pre-wrap text-brand-950 dark:bg-brand-400/15 dark:text-brand-50">
        {content}
      </p>
    </article>
  );
});
