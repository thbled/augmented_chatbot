import { describe, expect, it } from 'vitest';

import { streamOf } from '../test/streams';
import { readSseStream } from './sse';

describe('readSseStream', () => {
  it('parses events split across chunks', async () => {
    const events: unknown[] = [];
    await readSseStream(
      streamOf(['data: {"type":"del', 'ta","text":"é"}\n', '\ndata: {"type":"done"}\r\n\r\n']),
      (event) => events.push(event),
    );
    expect(events).toEqual([{ type: 'delta', text: 'é' }, { type: 'done' }]);
  });

  it('ignores comments and flushes a trailing event', async () => {
    const events: unknown[] = [];
    await readSseStream(streamOf([': ping\n\n', 'data: {"type":"done"}']), (event) =>
      events.push(event),
    );
    expect(events).toEqual([{ type: 'done' }]);
  });

  it('propagates errors thrown by the handler', async () => {
    await expect(
      readSseStream(streamOf(['data: {"type":"error"}\n\n']), () => {
        throw new Error('boom');
      }),
    ).rejects.toThrow('boom');
  });
});
