/**
 * Contrat des cartes affichées dans le chat. Le JSON est produit par
 * `tools/src/conference_tools/models.py` (méthodes `to_card`) et recopié par le LLM.
 */

export interface SessionReference {
  id?: string;
  title: string;
  date?: string;
  start?: string;
  end?: string;
  room?: string;
}

export interface SpeakerCardData {
  id?: string;
  firstName: string;
  lastName: string;
  jobTitle?: string;
  company?: string;
  photoUrl?: string;
  bio?: string;
  expertise?: string[];
  linkedinUrl?: string;
  sessions?: SessionReference[];
}

export interface SessionSpeaker {
  id?: string;
  name: string;
  photoUrl?: string;
}

export interface SessionCardData {
  id?: string;
  title: string;
  date?: string;
  start?: string;
  end?: string;
  room?: string;
  format?: string;
  track?: string;
  language?: string;
  summary?: string;
  tags?: string[];
  speakers?: SessionSpeaker[];
}

export interface PartnerCardData {
  id?: string;
  name: string;
  tier?: string;
  logoUrl?: string;
  websiteUrl?: string;
  sector?: string;
  summary?: string;
  booth?: string;
}

export type CardKind = 'speaker' | 'session' | 'partner';

export type CardSegment =
  | { kind: 'speaker'; data: SpeakerCardData }
  | { kind: 'session'; data: SessionCardData }
  | { kind: 'partner'; data: PartnerCardData };

export type MessageSegment =
  | { kind: 'markdown'; text: string }
  | CardSegment
  | { kind: 'pending'; card: CardKind | 'suggestions' };
