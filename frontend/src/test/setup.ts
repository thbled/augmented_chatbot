import '@testing-library/jest-dom/vitest';
import '../i18n';

import { cleanup } from '@testing-library/react';
import { afterEach, beforeEach } from 'vitest';

import i18n from '../i18n';

// jsdom n'implémente ni <dialog>.showModal ni matchMedia ni scrollTo.
HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
  this.open = true;
};
HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
  this.open = false;
  this.dispatchEvent(new Event('close'));
};
window.matchMedia = (query: string) =>
  ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    addListener: () => undefined,
    removeListener: () => undefined,
    dispatchEvent: () => false,
  }) as MediaQueryList;
Element.prototype.scrollTo = () => undefined;

beforeEach(async () => {
  localStorage.clear();
  await i18n.changeLanguage('fr');
});

afterEach(() => {
  cleanup();
});
