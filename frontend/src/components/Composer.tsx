import { ArrowUp, Square } from 'lucide-react';
import { useRef, useState, type FormEvent, type KeyboardEvent, type RefObject } from 'react';
import { useTranslation } from 'react-i18next';

import { MAX_MESSAGE_LENGTH } from '../config';

interface ComposerProps {
  inputRef?: RefObject<HTMLTextAreaElement | null>;
  busy: boolean;
  onSend: (text: string) => void;
  onStop: () => void;
}

const MAX_HEIGHT_PX = 160;
const COUNTER_THRESHOLD = MAX_MESSAGE_LENGTH - 200;

export function Composer({ inputRef, busy, onSend, onStop }: ComposerProps) {
  const { t } = useTranslation();
  const [value, setValue] = useState('');
  const localRef = useRef<HTMLTextAreaElement | null>(null);
  const remaining = MAX_MESSAGE_LENGTH - value.length;
  const showCounter = value.length > COUNTER_THRESHOLD;

  // Hauteur automatique, bornée.
  const resize = (textarea: HTMLTextAreaElement | null) => {
    if (!textarea) return;
    textarea.style.height = 'auto';
    textarea.style.height = `${Math.min(textarea.scrollHeight, MAX_HEIGHT_PX)}px`;
  };

  const submit = (event?: FormEvent) => {
    event?.preventDefault();
    if (busy || !value.trim()) return;
    onSend(value);
    setValue('');
    if (localRef.current) localRef.current.style.height = 'auto';
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    // Entrée envoie, Maj+Entrée ajoute une ligne (sauf pendant une composition IME).
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit();
    }
  };

  return (
    <form
      onSubmit={submit}
      className="mx-auto flex w-full max-w-3xl items-end gap-2 rounded-[1.75rem] border border-slate-300 bg-white p-1.5 pl-4 shadow-lg shadow-slate-900/5 transition-colors focus-within:border-brand-500 dark:border-white/15 dark:bg-slate-900 dark:shadow-none dark:focus-within:border-brand-400"
    >
      <label htmlFor="composer" className="sr-only">
        {t('composer.label')}
      </label>
      <textarea
        id="composer"
        ref={(node) => {
          localRef.current = node;
          if (inputRef) inputRef.current = node;
        }}
        rows={1}
        value={value}
        maxLength={MAX_MESSAGE_LENGTH}
        onChange={(event) => {
          setValue(event.target.value);
          resize(event.target);
        }}
        onKeyDown={onKeyDown}
        placeholder={t('composer.placeholder')}
        enterKeyHint="send"
        autoComplete="off"
        aria-describedby={showCounter ? 'composer-count' : undefined}
        className="max-h-40 min-h-11 flex-1 resize-none bg-transparent py-2.5 text-base leading-6 text-slate-900 placeholder:text-slate-500 focus:outline-none dark:text-white dark:placeholder:text-slate-400"
      />
      {showCounter && (
        <span id="composer-count" className="self-center text-xs text-slate-500 tabular-nums">
          {t('composer.remaining', { count: remaining })}
        </span>
      )}
      {busy ? (
        <button
          type="button"
          onClick={onStop}
          aria-label={t('composer.stop')}
          className="inline-flex size-11 shrink-0 items-center justify-center rounded-full bg-slate-900 text-white transition-colors hover:bg-slate-700 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200"
        >
          <Square aria-hidden="true" className="size-4 fill-current" />
        </button>
      ) : (
        <button
          type="submit"
          disabled={!value.trim()}
          aria-label={t('composer.send')}
          className="inline-flex size-11 shrink-0 items-center justify-center rounded-full bg-brand-700 text-white transition-colors hover:bg-brand-800 disabled:bg-slate-300 disabled:text-slate-600 dark:bg-brand-500 dark:hover:bg-brand-400 dark:disabled:bg-white/10 dark:disabled:text-slate-400"
        >
          <ArrowUp aria-hidden="true" className="size-5" />
        </button>
      )}
    </form>
  );
}
