import { ChevronRight, ExternalLink as ExternalIcon, Store } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { useChatActions } from '../../context/ChatActions';
import { initials, safeImageUrl } from '../../lib/urls';
import type { PartnerCardData } from '../../types/cards';
import { ExternalLink } from '../common/ExternalLink';

function PartnerLogo({ partner }: { partner: PartnerCardData }) {
  const url = safeImageUrl(partner.logoUrl);
  const [failed, setFailed] = useState(false);
  return (
    <span className="flex h-14 w-20 shrink-0 items-center justify-center rounded-xl border border-slate-200 bg-white p-2 dark:border-white/10">
      {url && !failed ? (
        <img
          src={url}
          alt=""
          loading="lazy"
          decoding="async"
          onError={() => setFailed(true)}
          className="max-h-full max-w-full object-contain"
        />
      ) : (
        <span aria-hidden="true" className="font-semibold text-slate-700">
          {initials(partner.name)}
        </span>
      )}
    </span>
  );
}

export function PartnerCard({ partner }: { partner: PartnerCardData }) {
  const { t } = useTranslation();
  const { ask, busy } = useChatActions();

  return (
    <article className="card flex h-full flex-col gap-3 p-4">
      <div className="flex items-center gap-3">
        <PartnerLogo partner={partner} />
        <div className="min-w-0">
          <h3 className="truncate text-base font-semibold text-slate-900 dark:text-white">
            {partner.name}
          </h3>
          {partner.sector && (
            <p className="line-clamp-1 text-sm text-slate-600 dark:text-slate-300">
              {partner.sector}
            </p>
          )}
        </div>
      </div>
      {(partner.tier || partner.booth) && (
        <ul className="flex flex-wrap gap-1.5">
          {partner.tier && <li className="tag">{partner.tier}</li>}
          {partner.booth && (
            <li className="tag gap-1">
              <Store aria-hidden="true" className="size-3.5" />
              {t('cards.booth', { booth: partner.booth })}
            </li>
          )}
        </ul>
      )}
      {partner.summary && (
        <p className="line-clamp-3 text-sm leading-relaxed text-slate-600 dark:text-slate-300">
          {partner.summary}
        </p>
      )}
      <div className="mt-auto flex flex-wrap items-center gap-x-1">
        <button
          type="button"
          className="link-button -ml-3"
          disabled={busy}
          onClick={() => ask(t('cards.questions.partner', { name: partner.name }))}
          aria-label={t('cards.askAboutItem', { name: partner.name })}
        >
          {t('cards.askAbout')}
          <ChevronRight aria-hidden="true" className="size-4" />
        </button>
        {partner.websiteUrl && (
          <ExternalLink href={partner.websiteUrl} className="link-button">
            {t('cards.website')}
            <ExternalIcon aria-hidden="true" className="size-4" />
          </ExternalLink>
        )}
      </div>
    </article>
  );
}
