import { act, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import App from './App';
import { STORAGE_KEYS } from './config';
import { ChatApiError, streamChat, type ChatPayload } from './lib/api';

vi.mock('./lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./lib/api')>();
  return { ...actual, streamChat: vi.fn<typeof actual.streamChat>() };
});

const mockedStream = vi.mocked(streamChat);

const SPEAKER = {
  id: 'ada-lovelace',
  firstName: 'Ada',
  lastName: 'Lovelace',
  jobTitle: 'Directrice scientifique',
  company: 'Analytical Engines',
  bio: 'Pionnière de la programmation.',
  expertise: ['IA générative'],
  linkedinUrl: 'https://www.linkedin.com/in/ada',
  sessions: [{ id: 's1', title: 'Keynote IA', date: '2026-11-12', start: '09:30', end: '10:15' }],
};

const ANSWER = [
  'Voici **Ada Lovelace** :\n\n',
  '```speaker\n' + JSON.stringify(SPEAKER) + '\n```\n\n',
  '```suggestions\n["Quelles sont ses sessions ?", "Qui d\'autre parle d\'IA ?"]\n```',
];

function payloadAt(index: number): ChatPayload {
  const call = mockedStream.mock.calls.at(index);
  if (!call) throw new Error(`Aucun appel à l'index ${index}`);
  return call[0];
}

function replyWith(chunks: string[]) {
  mockedStream.mockImplementation(async (_payload, { onDelta }) => {
    for (const chunk of chunks) onDelta(chunk);
  });
}

describe('App', () => {
  beforeEach(() => {
    mockedStream.mockReset();
  });

  it('shows the welcome screen with starter questions', () => {
    render(<App />);
    expect(screen.getByRole('heading', { level: 2, name: /Bienvenue/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Qui sont les speakers/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Nouvelle conversation' })).toBeDisabled();
  });

  it('sends a question and renders markdown, cards and suggestions', async () => {
    replyWith(ANSWER);
    const user = userEvent.setup();
    render(<App />);

    await user.type(screen.getByLabelText('Votre question'), 'Qui est Ada ?{Enter}');

    expect(await screen.findByRole('heading', { name: 'Ada Lovelace' })).toBeInTheDocument();
    expect(screen.getByText('Qui est Ada ?')).toBeInTheDocument();
    // Le rendu Markdown est chargé à la demande (texte brut en attendant).
    expect(await screen.findByText('Ada Lovelace', { selector: 'strong' })).toBeInTheDocument();
    expect(screen.getByLabelText('Votre question')).toHaveValue('');

    const payload = payloadAt(0);
    expect(payload).toEqual({
      locale: 'fr',
      messages: [{ role: 'user', content: 'Qui est Ada ?' }],
    });

    const suggestions = screen.getByRole('region', { name: 'Questions suggérées' });
    replyWith(['Elle anime la keynote.']);
    await user.click(
      within(suggestions).getByRole('button', { name: /Quelles sont ses sessions/ }),
    );

    expect(await screen.findByText('Elle anime la keynote.')).toBeInTheDocument();
    const history = payloadAt(1).messages;
    expect(history.map((m) => m.role)).toEqual(['user', 'assistant', 'user']);
    expect(history[1]?.content).toContain('```speaker');
  });

  it('opens the speaker profile dialog and asks about the speaker', async () => {
    replyWith(ANSWER);
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole('button', { name: /Qui sont les speakers/ }));

    await user.click(await screen.findByRole('button', { name: 'Voir la fiche de Ada Lovelace' }));
    const dialog = screen.getByRole('dialog', { name: 'Ada Lovelace' });
    expect(within(dialog).getByText('Pionnière de la programmation.')).toBeInTheDocument();
    expect(within(dialog).getByRole('link', { name: /Profil LinkedIn/ })).toHaveAttribute(
      'target',
      '_blank',
    );

    replyWith(['Ada est une pionnière.']);
    await user.click(within(dialog).getByRole('button', { name: /Poser une question sur Ada/ }));
    expect(dialog).not.toHaveAttribute('open');
    expect(await screen.findByText('Ada est une pionnière.')).toBeInTheDocument();
    const lastPayload = payloadAt(-1);
    expect(lastPayload.messages.at(-1)?.content).toMatch(/^Présente-moi Ada Lovelace/);
  });

  it('replaces streamed text with the final answer', async () => {
    mockedStream.mockImplementation(async (_payload, { onDelta, onReplace }) => {
      onDelta('Texte dans le désordre');
      onReplace?.('Texte final **complet**');
    });
    const user = userEvent.setup();
    render(<App />);
    await user.type(screen.getByLabelText('Votre question'), 'Bonjour{Enter}');
    expect(await screen.findByText('complet', { selector: 'strong' })).toBeInTheDocument();
    expect(screen.queryByText('Texte dans le désordre')).not.toBeInTheDocument();
  });

  it('sends the whole conversation', async () => {
    const user = userEvent.setup();
    render(<App />);
    for (let i = 0; i < 8; i++) {
      replyWith([`Réponse ${i}`]);
      await user.type(screen.getByLabelText('Votre question'), `Question ${i}{Enter}`);
      await screen.findByText(`Réponse ${i}`);
    }
    expect(payloadAt(-1).messages).toHaveLength(15);
  });

  it('shows a translated error and retries', async () => {
    mockedStream.mockRejectedValueOnce(new ChatApiError('llm_unavailable'));
    const user = userEvent.setup();
    render(<App />);
    await user.type(screen.getByLabelText('Votre question'), 'Bonjour{Enter}');

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('momentanément indisponible');

    replyWith(['Bonjour !']);
    await user.click(within(alert).getByRole('button', { name: 'Réessayer' }));
    expect(await screen.findByText('Bonjour !')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    // Le message en erreur n'est pas renvoyé au LLM.
    expect(payloadAt(1).messages).toEqual([{ role: 'user', content: 'Bonjour' }]);
  });

  it('does not offer retry when rate limited', async () => {
    mockedStream.mockRejectedValueOnce(new ChatApiError('rate_limited'));
    const user = userEvent.setup();
    render(<App />);
    await user.type(screen.getByLabelText('Votre question'), 'Bonjour{Enter}');
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('nombre maximal de questions');
    expect(within(alert).queryByRole('button')).not.toBeInTheDocument();
  });

  it('stops a streaming answer', async () => {
    mockedStream.mockImplementation(
      (_payload, { signal, onDelta }) =>
        new Promise((_resolve, reject) => {
          onDelta('Début de réponse');
          signal?.addEventListener('abort', () =>
            reject(new DOMException('Aborted', 'AbortError')),
          );
        }),
    );
    const user = userEvent.setup();
    render(<App />);
    await user.type(screen.getByLabelText('Votre question'), 'Bonjour{Enter}');

    await user.click(await screen.findByRole('button', { name: 'Arrêter la réponse' }));
    expect(await screen.findByText('Réponse interrompue.')).toBeInTheDocument();
    expect(screen.getByText('Début de réponse')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Envoyer' })).toBeInTheDocument();
  });

  it('persists the conversation and resets it', async () => {
    replyWith(['Réponse enregistrée.']);
    const user = userEvent.setup();
    const { unmount } = render(<App />);
    await user.type(screen.getByLabelText('Votre question'), 'Bonjour{Enter}');
    await screen.findByText('Réponse enregistrée.');
    await waitFor(() =>
      expect(localStorage.getItem(STORAGE_KEYS.conversation)).toContain('Bonjour'),
    );

    unmount();
    render(<App />);
    expect(screen.getByText('Réponse enregistrée.')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Nouvelle conversation' }));
    expect(screen.getByRole('heading', { name: /Bienvenue/ })).toBeInTheDocument();
    expect(localStorage.getItem(STORAGE_KEYS.conversation)).toBeNull();
    expect(screen.getByLabelText('Votre question')).toHaveFocus();
  });

  it('switches language and theme', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole('button', { name: 'Switch to English' }));
    expect(await screen.findByRole('heading', { name: /Welcome to/ })).toBeInTheDocument();
    expect(document.documentElement.lang).toBe('en');
    expect(localStorage.getItem(STORAGE_KEYS.language)).toBe('en');

    await user.click(screen.getByRole('button', { name: 'Switch to dark theme' }));
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(localStorage.getItem(STORAGE_KEYS.theme)).toBe('dark');
    expect(screen.getByRole('button', { name: 'Switch to light theme' })).toBeInTheDocument();

    await act(async () => {
      await user.click(screen.getByRole('button', { name: 'Passer en français' }));
    });
    expect(document.documentElement.lang).toBe('fr');
  });

  it('sends the current locale to the API', async () => {
    replyWith(['Hello!']);
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole('button', { name: 'Switch to English' }));
    await user.type(screen.getByLabelText('Your question'), 'Hi{Enter}');
    await screen.findByText('Hello!');
    expect(payloadAt(0).locale).toBe('en');
  });
});
