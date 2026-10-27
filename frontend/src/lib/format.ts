import type { Locale } from '../types/chat';

/** Formate une date ISO `AAAA-MM-JJ` (sans fuseau) : « jeu. 12 nov. ». */
export function formatDay(isoDate: string | undefined, locale: Locale): string | undefined {
  const match = isoDate?.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return undefined;
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  return new Intl.DateTimeFormat(locale, {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  }).format(date);
}

export function formatTimeRange(start?: string, end?: string): string | undefined {
  if (start && end) return `${start} – ${end}`;
  return start ?? undefined;
}

/** Espace insécable avant « ? ! : ; » pour éviter une ponctuation orpheline en fin de ligne. */
export function frenchSpacing(text: string): string {
  return text.replace(/ ([?!:;»])/g, '\u00a0$1').replace(/« /g, '«\u00a0');
}
