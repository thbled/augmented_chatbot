import { describe, expect, it } from 'vitest';

import { safeImageUrl, safeUrl } from './urls';

describe('safeUrl', () => {
  it('accepts http(s) and site-relative paths only', () => {
    expect(safeUrl('https://example.com/a')).toBe('https://example.com/a');
    expect(safeUrl('/images/a.jpg')).toBe('/images/a.jpg');
    expect(safeUrl('//evil.test/a')).toBeUndefined();
    expect(safeUrl('javascript:alert(1)')).toBeUndefined();
  });
});

describe('safeImageUrl', () => {
  const hosts = ['cdn.example.com'];

  it('accepts application images and allowed hosts', () => {
    expect(safeImageUrl('/images/speakers/ada.jpg', hosts)).toBe('/images/speakers/ada.jpg');
    expect(safeImageUrl('https://cdn.example.com/ada.jpg', hosts)).toBe(
      'https://cdn.example.com/ada.jpg',
    );
  });

  it('rejects other hosts, plain http and invalid URLs', () => {
    expect(safeImageUrl('https://attacker.test/pixel?q=secret', hosts)).toBeUndefined();
    expect(safeImageUrl('http://cdn.example.com/ada.jpg', hosts)).toBeUndefined();
    expect(safeImageUrl('https://cdn.example.com.attacker.test/a.jpg', hosts)).toBeUndefined();
    expect(safeImageUrl('https://', hosts)).toBeUndefined();
  });

  it('rejects every external image when no host is allowed', () => {
    expect(safeImageUrl('https://cdn.example.com/ada.jpg', [])).toBeUndefined();
  });
});
