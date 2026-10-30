import { AxiosError, AxiosHeaders } from 'axios';
import { describe, expect, it, vi } from 'vitest';

import { streamOf } from '../test/streams';
import { apiClient, ChatApiError, errorFromStatus, streamChat } from './api';

const payload = { locale: 'fr' as const, messages: [{ role: 'user' as const, content: 'Salut' }] };

function mockStream(chunks: string[]) {
  return vi.spyOn(apiClient, 'post').mockResolvedValue({ data: streamOf(chunks) });
}

describe('streamChat', () => {
  it('forwards deltas and resolves on done', async () => {
    const post = mockStream([
      'data: {"type":"delta","text":"Bon"}\n\n',
      'data: {"type":"delta","text":"jour"}\n\ndata: {"type":"done"}\n\n',
    ]);
    const deltas: string[] = [];
    await streamChat(payload, { onDelta: (text) => deltas.push(text) });
    expect(deltas.join('')).toBe('Bonjour');
    expect(post).toHaveBeenCalledWith(
      '/chat',
      payload,
      expect.objectContaining({ adapter: 'fetch', responseType: 'stream' }),
    );
  });

  it('forwards replace events', async () => {
    mockStream([
      'data: {"type":"delta","text":"Bon"}\n\n',
      'data: {"type":"replace","text":"Bonjour complet"}\n\ndata: {"type":"done"}\n\n',
    ]);
    const received: string[] = [];
    await streamChat(payload, {
      onDelta: (text) => received.push(`delta:${text}`),
      onReplace: (text) => received.push(`replace:${text}`),
    });
    expect(received).toEqual(['delta:Bon', 'replace:Bonjour complet']);
  });

  it('rejects with the server error code', async () => {
    mockStream(['data: {"type":"error","code":"llm_timeout"}\n\n']);
    await expect(streamChat(payload, { onDelta: () => undefined })).rejects.toMatchObject({
      code: 'llm_timeout',
    });
  });

  it('rejects when the stream ends without done', async () => {
    mockStream(['data: {"type":"delta","text":"Bon"}\n\n']);
    await expect(streamChat(payload, { onDelta: () => undefined })).rejects.toEqual(
      new ChatApiError('interrupted'),
    );
  });

  it('maps HTTP errors', async () => {
    const error = new AxiosError('Too many', 'ERR_BAD_REQUEST', undefined, undefined, {
      status: 429,
      statusText: '',
      data: null,
      headers: {},
      config: { headers: new AxiosHeaders() },
    });
    vi.spyOn(apiClient, 'post').mockRejectedValue(error);
    await expect(streamChat(payload, { onDelta: () => undefined })).rejects.toMatchObject({
      code: 'rate_limited',
    });
  });
});

describe('errorFromStatus', () => {
  it.each([
    [429, 'rate_limited'],
    [413, 'message_too_long'],
    [400, 'invalid_request'],
    [502, 'llm_unavailable'],
    [undefined, 'network'],
  ])('%s → %s', (status, code) => {
    expect(errorFromStatus(status)).toBe(code);
  });
});
