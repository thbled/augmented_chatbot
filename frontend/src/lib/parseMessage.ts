import type {
  CardKind,
  CardSegment,
  MessageSegment,
  PartnerCardData,
  SessionCardData,
  SessionReference,
  SessionSpeaker,
  SpeakerCardData,
} from '../types/cards';

export interface ParsedMessage {
  segments: MessageSegment[];
  suggestions: string[];
}

const BLOCK_KINDS = ['speaker', 'session', 'partner', 'suggestions'] as const;
type BlockKind = (typeof BLOCK_KINDS)[number];

const CLOSED_BLOCK = /```(speaker|session|partner|suggestions)[ \t]*\n([\s\S]*?)\n?```/g;
const OPEN_BLOCK = /```(speaker|session|partner|suggestions)\b/;
const TRAILING_PARTIAL_FENCE = /\n?`{1,3}[a-z]*$/;

const MAX_SUGGESTIONS = 4;
const MAX_SUGGESTION_LENGTH = 120;

type Json = Record<string, unknown>;

const isObject = (value: unknown): value is Json =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const str = (value: unknown): string | undefined =>
  typeof value === 'string' && value.trim() ? value.trim() : undefined;

const strList = (value: unknown): string[] | undefined => {
  if (!Array.isArray(value)) return undefined;
  const items = value.map(str).filter((item): item is string => Boolean(item));
  return items.length ? items : undefined;
};

const objList = <T>(value: unknown, map: (item: Json) => T | undefined): T[] | undefined => {
  if (!Array.isArray(value)) return undefined;
  const items = value
    .filter(isObject)
    .map(map)
    .filter((item): item is T => item !== undefined);
  return items.length ? items : undefined;
};

function toSessionReference(raw: Json): SessionReference | undefined {
  const title = str(raw.title);
  if (!title) return undefined;
  return {
    id: str(raw.id),
    title,
    date: str(raw.date),
    start: str(raw.start),
    end: str(raw.end),
    room: str(raw.room),
  };
}

function toSessionSpeaker(raw: Json): SessionSpeaker | undefined {
  const name = str(raw.name);
  if (!name) return undefined;
  return { id: str(raw.id), name, photoUrl: str(raw.photoUrl) };
}

export function toSpeaker(raw: Json): SpeakerCardData | undefined {
  let firstName = str(raw.firstName);
  let lastName = str(raw.lastName);
  const name = str(raw.name);
  if ((!firstName || !lastName) && name) {
    const [first, ...rest] = name.split(/\s+/);
    firstName = first;
    lastName = rest.join(' ');
  }
  if (!firstName) return undefined;
  return {
    id: str(raw.id),
    firstName,
    lastName: lastName ?? '',
    jobTitle: str(raw.jobTitle),
    company: str(raw.company),
    photoUrl: str(raw.photoUrl),
    bio: str(raw.bio),
    expertise: strList(raw.expertise),
    linkedinUrl: str(raw.linkedinUrl),
    sessions: objList(raw.sessions, toSessionReference),
  };
}

export function toSession(raw: Json): SessionCardData | undefined {
  const title = str(raw.title);
  if (!title) return undefined;
  return {
    id: str(raw.id),
    title,
    date: str(raw.date),
    start: str(raw.start),
    end: str(raw.end),
    room: str(raw.room),
    format: str(raw.format),
    track: str(raw.track),
    language: str(raw.language),
    summary: str(raw.summary) ?? str(raw.description),
    tags: strList(raw.tags),
    speakers: objList(raw.speakers, toSessionSpeaker),
  };
}

export function toPartner(raw: Json): PartnerCardData | undefined {
  const name = str(raw.name);
  if (!name) return undefined;
  return {
    id: str(raw.id),
    name,
    tier: str(raw.tier),
    logoUrl: str(raw.logoUrl),
    websiteUrl: str(raw.websiteUrl),
    sector: str(raw.sector),
    summary: str(raw.summary) ?? str(raw.description),
    booth: str(raw.booth),
  };
}

function parseJson(body: string): unknown {
  try {
    return JSON.parse(body.trim());
  } catch {
    return undefined;
  }
}

function parseCards(kind: CardKind, body: string): CardSegment[] {
  const value = parseJson(body);
  const items = (Array.isArray(value) ? value : [value]).filter(isObject);
  const cards: CardSegment[] = [];
  for (const item of items) {
    if (kind === 'speaker') {
      const data = toSpeaker(item);
      if (data) cards.push({ kind, data });
    } else if (kind === 'session') {
      const data = toSession(item);
      if (data) cards.push({ kind, data });
    } else {
      const data = toPartner(item);
      if (data) cards.push({ kind, data });
    }
  }
  return cards;
}

function parseSuggestions(body: string): string[] {
  const value = parseJson(body);
  const raw = Array.isArray(value)
    ? value
    : body
        .split('\n')
        .map((line) => line.replace(/^\s*(?:[-*•]|\d+[.)])\s*/, '').replace(/^"|",?$/g, ''));
  return raw
    .map(str)
    .filter((item): item is string => item !== undefined && item.length <= MAX_SUGGESTION_LENGTH);
}

function pushMarkdown(segments: MessageSegment[], text: string) {
  if (!text.trim()) return;
  const last = segments.at(-1);
  if (last?.kind === 'markdown') {
    last.text += text;
  } else {
    segments.push({ kind: 'markdown', text });
  }
}

function cardKey(card: CardSegment): string {
  const data = card.data as { id?: string; title?: string; name?: string; firstName?: string };
  return `${card.kind}:${data.id ?? data.title ?? data.name ?? data.firstName}`;
}

/**
 * Découpe la réponse de l'assistant en texte Markdown, cartes et suggestions.
 * Pendant le streaming, un bloc non encore fermé devient un segment `pending`
 * (affiché comme squelette) au lieu d'exposer du JSON partiel.
 */
export function parseAssistantMessage(content: string, streaming = false): ParsedMessage {
  const segments: MessageSegment[] = [];
  const suggestions: string[] = [];
  const seenCards = new Set<string>();
  let cursor = 0;

  for (const match of content.matchAll(CLOSED_BLOCK)) {
    pushMarkdown(segments, content.slice(cursor, match.index));
    cursor = match.index + match[0].length;
    const kind = match[1] as BlockKind;
    const body = match[2] ?? '';
    if (kind === 'suggestions') {
      suggestions.push(...parseSuggestions(body));
      continue;
    }
    for (const card of parseCards(kind, body)) {
      const key = cardKey(card);
      if (seenCards.has(key)) continue;
      seenCards.add(key);
      segments.push(card);
    }
  }

  let rest = content.slice(cursor);
  const open = OPEN_BLOCK.exec(rest);
  if (open) {
    pushMarkdown(segments, rest.slice(0, open.index));
    if (streaming) segments.push({ kind: 'pending', card: open[1] as BlockKind });
  } else {
    if (streaming) rest = rest.replace(TRAILING_PARTIAL_FENCE, '');
    pushMarkdown(segments, rest);
  }

  return { segments, suggestions: [...new Set(suggestions)].slice(0, MAX_SUGGESTIONS) };
}

/** Version texte d'une réponse, pour l'annonce aux lecteurs d'écran. */
export function toPlainText(parsed: ParsedMessage): string {
  return parsed.segments
    .map((segment) => {
      switch (segment.kind) {
        case 'markdown':
          return segment.text
            .replace(/!\[[^\]]*\]\([^)]*\)/g, '')
            .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
            .replace(/[*_#>`|]/g, '')
            .replace(/\s+/g, ' ')
            .trim();
        case 'speaker':
          return `${segment.data.firstName} ${segment.data.lastName}`.trim();
        case 'session':
          return segment.data.title;
        case 'partner':
          return segment.data.name;
        default:
          return '';
      }
    })
    .filter(Boolean)
    .join('. ');
}
