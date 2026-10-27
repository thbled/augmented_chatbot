import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

import { safeUrl } from '../../lib/urls';

interface ExternalLinkProps {
  href?: string;
  children: ReactNode;
  className?: string;
}

/** Lien s'ouvrant dans un nouvel onglet, signalé aux technologies d'assistance. */
export function ExternalLink({ href, children, className }: ExternalLinkProps) {
  const { t } = useTranslation();
  const url = safeUrl(href);
  if (!url) return <>{children}</>;
  return (
    <a href={url} target="_blank" rel="noopener noreferrer" className={className}>
      {children}
      <span className="sr-only"> {t('cards.newWindow')}</span>
    </a>
  );
}
