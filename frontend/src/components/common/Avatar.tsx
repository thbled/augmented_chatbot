import { useState } from 'react';

import { initials, safeUrl } from '../../lib/urls';

interface AvatarProps {
  name: string;
  src?: string;
  className?: string;
}

/** Photo décorative (le nom est toujours affiché à côté), avec initiales en repli. */
export function Avatar({ name, src, className = 'size-12' }: AvatarProps) {
  const url = safeUrl(src);
  const [failed, setFailed] = useState(false);

  if (url && !failed) {
    return (
      <img
        src={url}
        alt=""
        loading="lazy"
        decoding="async"
        onError={() => setFailed(true)}
        className={`${className} shrink-0 rounded-full bg-slate-200 object-cover ring-2 ring-white dark:bg-slate-800 dark:ring-slate-900`}
      />
    );
  }
  return (
    <span
      aria-hidden="true"
      className={`${className} inline-flex shrink-0 items-center justify-center rounded-full bg-brand-100 font-semibold text-brand-800 ring-2 ring-white dark:bg-brand-900 dark:text-brand-100 dark:ring-slate-900`}
    >
      {initials(name)}
    </span>
  );
}
