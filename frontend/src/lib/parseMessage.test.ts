import { describe, expect, it } from 'vitest';

import { parseAssistantMessage, toPlainText } from './parseMessage';

const speaker = {
  id: 'ada-lovelace',
  firstName: 'Ada',
  lastName: 'Lovelace',
  jobTitle: 'Directrice scientifique',
  expertise: ['IA', 'Maths'],
};

const block = (kind: string, value: unknown) => `\`\`\`${kind}\n${JSON.stringify(value)}\n\`\`\``;

describe('parseAssistantMessage', () => {
  it('returns plain markdown when there is no block', () => {
    expect(parseAssistantMessage('**Bonjour** !')).toEqual({
      segments: [{ kind: 'markdown', text: '**Bonjour** !' }],
      suggestions: [],
    });
  });

  it('extracts cards between markdown segments', () => {
    const content = `Voici la speaker :\n\n${block('speaker', speaker)}\n\nElle intervient à 9h.`;
    const { segments } = parseAssistantMessage(content);
    expect(segments.map((s) => s.kind)).toEqual(['markdown', 'speaker', 'markdown']);
    expect(segments[1]).toMatchObject({ kind: 'speaker', data: { firstName: 'Ada' } });
  });

  it('supports arrays, deduplicates and ignores invalid cards', () => {
    const content = [
      block('session', [{ id: 's1', title: 'Keynote' }, { id: 's2' }]),
      block('session', { id: 's1', title: 'Keynote' }),
      block('partner', { name: 'Acme', tier: 'Gold' }),
      '```speaker\n{pas du json}\n```',
    ].join('\n');
    const { segments } = parseAssistantMessage(content);
    expect(segments).toEqual([
      expect.objectContaining({ kind: 'session', data: expect.objectContaining({ id: 's1' }) }),
      expect.objectContaining({ kind: 'partner', data: expect.objectContaining({ name: 'Acme' }) }),
    ]);
  });

  it('accepts a speaker described by a single name field', () => {
    const { segments } = parseAssistantMessage(block('speaker', { name: 'Alan Mathison Turing' }));
    expect(segments[0]).toMatchObject({
      data: { firstName: 'Alan', lastName: 'Mathison Turing' },
    });
  });

  it('extracts suggestions, limited to four unique items', () => {
    const list = ['A ?', 'B ?', 'A ?', 'C ?', 'D ?', 'E ?'];
    const parsed = parseAssistantMessage(`Réponse.\n\n${block('suggestions', list)}`);
    expect(parsed.suggestions).toEqual(['A ?', 'B ?', 'C ?', 'D ?']);
    expect(parsed.segments).toEqual([{ kind: 'markdown', text: 'Réponse.\n\n' }]);
  });

  it('falls back to a bullet list for malformed suggestions', () => {
    const parsed = parseAssistantMessage('```suggestions\n- Première ?\n- Seconde ?\n```');
    expect(parsed.suggestions).toEqual(['Première ?', 'Seconde ?']);
  });

  it('shows a pending placeholder for an unfinished block while streaming', () => {
    const content = 'Voici :\n\n```speaker\n{"id":"ada","firstNa';
    expect(parseAssistantMessage(content, true).segments).toEqual([
      { kind: 'markdown', text: 'Voici :\n\n' },
      { kind: 'pending', card: 'speaker' },
    ]);
    // Une fois la réponse terminée, un bloc incomplet est simplement ignoré.
    expect(parseAssistantMessage(content, false).segments).toEqual([
      { kind: 'markdown', text: 'Voici :\n\n' },
    ]);
  });

  it('hides a partially received fence while streaming', () => {
    expect(parseAssistantMessage('Texte\n``', true).segments).toEqual([
      { kind: 'markdown', text: 'Texte' },
    ]);
  });

  it('removes document citations, including a partial one while streaming', () => {
    expect(parseAssistantMessage('Session à 14h [Doc 1]. Salle A [Doc 2, 3].').segments).toEqual([
      { kind: 'markdown', text: 'Session à 14h. Salle A.' },
    ]);
    expect(parseAssistantMessage('Titre « IA » [Do', true).segments).toEqual([
      { kind: 'markdown', text: 'Titre « IA »' },
    ]);
  });

  it('keeps regular code blocks as markdown', () => {
    const content = '```python\nprint(1)\n```';
    expect(parseAssistantMessage(content).segments).toEqual([{ kind: 'markdown', text: content }]);
  });
});

describe('toPlainText', () => {
  it('flattens markdown and cards for screen readers', () => {
    const parsed = parseAssistantMessage(
      `## Titre\n**Gras** et [lien](https://x.y)\n\n${block('speaker', speaker)}`,
    );
    expect(toPlainText(parsed)).toBe('Titre Gras et lien. Ada Lovelace');
  });
});
