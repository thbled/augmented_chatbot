import { createContext, useContext } from 'react';

import type { SpeakerCardData } from '../types/cards';

export interface ChatActions {
  /** Envoie une question dans la conversation. */
  ask: (question: string) => void;
  /** Ouvre la fiche détaillée d'un speaker. */
  openSpeaker: (speaker: SpeakerCardData) => void;
  /** Vrai pendant la génération d'une réponse (les actions d'envoi sont alors inactives). */
  busy: boolean;
}

const noop = () => undefined;

export const ChatActionsContext = createContext<ChatActions>({
  ask: noop,
  openSpeaker: noop,
  busy: false,
});

export const useChatActions = () => useContext(ChatActionsContext);
