import i18n from 'i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import { initReactI18next } from 'react-i18next';

import { STORAGE_KEYS } from '../config';
import type { Locale } from '../types/chat';
import en from './en.json';
import fr from './fr.json';

export const SUPPORTED_LOCALES: Locale[] = ['fr', 'en'];

export function currentLocale(): Locale {
  return i18n.resolvedLanguage === 'en' ? 'en' : 'fr';
}

void i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: { fr: { translation: fr }, en: { translation: en } },
    fallbackLng: 'fr',
    supportedLngs: SUPPORTED_LOCALES,
    nonExplicitSupportedLngs: true,
    load: 'languageOnly',
    interpolation: { escapeValue: false },
    detection: {
      // Français par défaut : l'anglais n'est utilisé que s'il a été choisi explicitement.
      order: ['localStorage'],
      lookupLocalStorage: STORAGE_KEYS.language,
      caches: ['localStorage'],
    },
  });

const syncDocumentLanguage = () => {
  document.documentElement.lang = currentLocale();
};
syncDocumentLanguage();
i18n.on('languageChanged', syncDocumentLanguage);

export default i18n;
