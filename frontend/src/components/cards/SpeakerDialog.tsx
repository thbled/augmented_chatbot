import { CalendarClock, MapPin, MessageCircleQuestion, X } from 'lucide-react';
import { useEffect, useId, useRef } from 'react';
import { useTranslation } from 'react-i18next';

import { useChatActions } from '../../context/ChatActions';
import { formatDay, formatTimeRange } from '../../lib/format';
import type { SpeakerCardData } from '../../types/cards';
import type { Locale } from '../../types/chat';
import { Avatar } from '../common/Avatar';
import { ExternalLink } from '../common/ExternalLink';
import { LinkedinIcon } from '../common/LinkedinIcon';
import { speakerName, speakerRole } from './SpeakerCard';

interface SpeakerDialogProps {
  speaker: SpeakerCardData | null;
  onClose: () => void;
}

/**
 * Fiche détaillée d'un speaker dans une boîte de dialogue modale native
 * (piège du focus, touche Échap et restitution du focus gérés par le navigateur).
 */
export function SpeakerDialog({ speaker, onClose }: SpeakerDialogProps) {
  const { t, i18n } = useTranslation();
  const { ask, busy } = useChatActions();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const locale: Locale = i18n.resolvedLanguage === 'en' ? 'en' : 'fr';

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (speaker && !dialog.open) dialog.showModal();
    if (!speaker && dialog.open) dialog.close();
  }, [speaker]);

  const name = speaker ? speakerName(speaker) : '';
  const role = speaker ? speakerRole(speaker) : '';

  const askAndClose = (question: string) => {
    onClose();
    ask(question);
  };

  return (
    // Le clic sur le fond est un raccourci souris ; au clavier, Échap ferme nativement le dialogue.
    // oxlint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-noninteractive-element-interactions
    <dialog
      ref={dialogRef}
      aria-labelledby={titleId}
      onClose={onClose}
      onClick={(event) => {
        // Clic sur le fond (hors contenu) : fermeture.
        if (event.target === dialogRef.current) onClose();
      }}
      className="m-0 mt-auto max-h-[92dvh] w-full max-w-none overflow-hidden rounded-t-3xl bg-white p-0 text-slate-900 shadow-2xl backdrop:bg-slate-950/50 backdrop:backdrop-blur-sm sm:m-auto sm:max-w-lg sm:rounded-3xl dark:bg-slate-900 dark:text-slate-100"
    >
      {speaker && (
        <div className="flex max-h-[92dvh] flex-col">
          <div className="flex items-start gap-4 border-b border-slate-200 p-5 dark:border-white/10">
            <Avatar name={name} src={speaker.photoUrl} className="size-20 text-2xl" />
            <div className="min-w-0 flex-1 pt-1">
              <h2 id={titleId} className="text-xl font-semibold tracking-tight">
                {name}
              </h2>
              {role && <p className="mt-0.5 text-sm text-slate-600 dark:text-slate-300">{role}</p>}
              {speaker.linkedinUrl && (
                <ExternalLink href={speaker.linkedinUrl} className="link-button mt-1 -ml-3 text-sm">
                  <LinkedinIcon className="size-4" />
                  {t('cards.linkedin')}
                </ExternalLink>
              )}
            </div>
            <button
              type="button"
              className="icon-button -mt-1 -mr-2"
              onClick={onClose}
              aria-label={t('cards.close')}
            >
              <X aria-hidden="true" className="size-5" />
            </button>
          </div>

          <div className="space-y-6 overflow-y-auto overscroll-contain p-5">
            {speaker.expertise && (
              <section>
                <h3 className="mb-2 text-xs font-semibold tracking-wider text-slate-500 uppercase dark:text-slate-400">
                  {t('cards.expertise')}
                </h3>
                <ul className="flex flex-wrap gap-1.5">
                  {speaker.expertise.map((item) => (
                    <li key={item} className="tag">
                      {item}
                    </li>
                  ))}
                </ul>
              </section>
            )}
            {speaker.bio && (
              <section>
                <h3 className="mb-2 text-xs font-semibold tracking-wider text-slate-500 uppercase dark:text-slate-400">
                  {t('cards.biography')}
                </h3>
                <p className="leading-relaxed text-slate-700 dark:text-slate-200">{speaker.bio}</p>
              </section>
            )}
            {speaker.sessions && (
              <section>
                <h3 className="mb-2 text-xs font-semibold tracking-wider text-slate-500 uppercase dark:text-slate-400">
                  {t('cards.sessions')}
                </h3>
                <ul className="space-y-2">
                  {speaker.sessions.map((session) => (
                    <li key={session.id ?? session.title}>
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() =>
                          askAndClose(t('cards.questions.session', { title: session.title }))
                        }
                        className="w-full rounded-xl border border-slate-200 p-3 text-left transition-colors hover:border-brand-300 hover:bg-brand-50/60 disabled:cursor-not-allowed disabled:opacity-60 dark:border-white/10 dark:hover:border-brand-400/40 dark:hover:bg-brand-400/10"
                      >
                        <span className="block font-medium">{session.title}</span>
                        <span className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-sm text-slate-600 dark:text-slate-300">
                          {(session.date || session.start) && (
                            <span className="inline-flex items-center gap-1">
                              <CalendarClock aria-hidden="true" className="size-4" />
                              {[
                                formatDay(session.date, locale),
                                formatTimeRange(session.start, session.end),
                              ]
                                .filter(Boolean)
                                .join(' · ')}
                            </span>
                          )}
                          {session.room && (
                            <span className="inline-flex items-center gap-1">
                              <MapPin aria-hidden="true" className="size-4" />
                              {session.room}
                            </span>
                          )}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </div>

          <div className="pb-safe border-t border-slate-200 p-4 dark:border-white/10">
            <button
              type="button"
              disabled={busy}
              onClick={() => askAndClose(t('cards.questions.speaker', { name }))}
              className="inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-full bg-brand-700 px-5 font-semibold text-white transition-colors hover:bg-brand-800 disabled:opacity-60 dark:bg-brand-500 dark:hover:bg-brand-400"
            >
              <MessageCircleQuestion aria-hidden="true" className="size-5" />
              {t('cards.askSpeaker', { name })}
            </button>
          </div>
        </div>
      )}
    </dialog>
  );
}
