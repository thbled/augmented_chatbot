/**
 * Lit un flux Server-Sent Events et appelle `onEvent` avec chaque charge utile JSON.
 * Seules les lignes `data:` sont prises en compte (format émis par l'API Flask).
 */
export async function readSseStream(
  stream: ReadableStream<Uint8Array>,
  onEvent: (payload: unknown) => void,
): Promise<void> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  const flush = (block: string) => {
    const data = block
      .split('\n')
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).trimStart())
      .join('\n');
    if (data) onEvent(JSON.parse(data));
  };

  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n?/g, '\n');
      let boundary = buffer.indexOf('\n\n');
      while (boundary !== -1) {
        flush(buffer.slice(0, boundary));
        buffer = buffer.slice(boundary + 2);
        boundary = buffer.indexOf('\n\n');
      }
    }
    buffer += decoder.decode();
    if (buffer.trim()) flush(buffer);
  } finally {
    reader.releaseLock();
  }
}
