import { ChevronRight } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { useChatActions } from '../../context/ChatActions';
import type { SpeakerCardData } from '../../types/cards';
import { Avatar } from '../common/Avatar';

export function speakerName(speaker: SpeakerCardData): string {
  return `${speaker.firstName} ${speaker.lastName}`.trim();
}

export function speakerRole(speaker: SpeakerCardData): string {
  return [speaker.jobTitle, speaker.company].filter(Boolean).join(' · ');
}

export function SpeakerCard({ speaker }: { speaker: SpeakerCardData }) {
  const { t } = useTranslation();
  const { openSpeaker } = useChatActions();
  const name = speakerName(speaker);
  const role = speakerRole(speaker);

  return (
    <article className="card flex h-full flex-col gap-3 p-4">
      <div className="flex items-center gap-3">
        <Avatar name={name} src={speaker.photoUrl} className="size-14 text-lg" />
        <div className="min-w-0">
          <h3 className="truncate text-base font-semibold text-slate-900 dark:text-white">
            {name}
          </h3>
          {role && (
            <p className="line-clamp-2 text-sm text-slate-600 dark:text-slate-300">{role}</p>
          )}
        </div>
      </div>
      {speaker.expertise && (
        <ul className="flex flex-wrap gap-1.5" aria-label={t('cards.expertise')}>
          {speaker.expertise.slice(0, 3).map((item) => (
            <li key={item} className="tag">
              {item}
            </li>
          ))}
        </ul>
      )}
      <div className="mt-auto">
        <button
          type="button"
          className="link-button -ml-3"
          onClick={() => openSpeaker(speaker)}
          aria-label={t('cards.viewProfileOf', { name })}
        >
          {t('cards.viewProfile')}
          <ChevronRight aria-hidden="true" className="size-4" />
        </button>
      </div>
    </article>
  );
}
