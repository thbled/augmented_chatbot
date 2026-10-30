/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_EVENT_NAME?: string;
  readonly VITE_API_BASE_URL?: string;
  /** Domaines autorisés pour les images, séparés par des virgules. */
  readonly VITE_IMAGE_HOSTS?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
