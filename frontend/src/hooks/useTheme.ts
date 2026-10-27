import { useCallback, useEffect, useState } from 'react';

import { STORAGE_KEYS } from '../config';
import { readString, writeString } from '../lib/storage';

export type Theme = 'light' | 'dark';

const THEME_COLORS: Record<Theme, string> = { light: '#f8fafc', dark: '#0b1020' };
const DARK_QUERY = '(prefers-color-scheme: dark)';

function storedTheme(): Theme | null {
  const value = readString(STORAGE_KEYS.theme);
  return value === 'light' || value === 'dark' ? value : null;
}

function systemTheme(): Theme {
  return window.matchMedia?.(DARK_QUERY).matches ? 'dark' : 'light';
}

function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme;
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', THEME_COLORS[theme]);
}

/**
 * Thème clair/sombre : suit le système tant que l'utilisateur n'a pas fait de choix
 * explicite, qui est alors mémorisé.
 */
export function useTheme() {
  const [explicit, setExplicit] = useState<Theme | null>(storedTheme);
  const [system, setSystem] = useState<Theme>(systemTheme);
  const theme = explicit ?? system;

  useEffect(() => {
    const media = window.matchMedia?.(DARK_QUERY);
    if (!media) return undefined;
    const onChange = (event: MediaQueryListEvent) => setSystem(event.matches ? 'dark' : 'light');
    media.addEventListener('change', onChange);
    return () => media.removeEventListener('change', onChange);
  }, []);

  useEffect(() => applyTheme(theme), [theme]);

  const toggle = useCallback(() => {
    const next: Theme = theme === 'dark' ? 'light' : 'dark';
    writeString(STORAGE_KEYS.theme, next);
    setExplicit(next);
  }, [theme]);

  return { theme, toggle };
}
