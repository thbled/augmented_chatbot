/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_EVENT_NAME?: string;
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
