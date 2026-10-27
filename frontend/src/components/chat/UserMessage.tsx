import { memo } from 'react';
import { useTranslation } from 'react-i18next';

export const UserMessage = memo(function UserMessage({ content }: { content: string }) {
  const { t } = useTranslation();
  return (
    <article className="flex animate-fade-in justify-end">
      <h2 className="sr-only">{t('chat.you')}</h2>
      <p className="max-w-[85%] rounded-3xl rounded-br-lg bg-brand-700 px-4 py-2.5 leading-relaxed break-words whitespace-pre-wrap text-white shadow-sm dark:bg-brand-600">
        {content}
      </p>
    </article>
  );
});
