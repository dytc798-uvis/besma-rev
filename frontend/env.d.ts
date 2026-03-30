/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_DEMO_PILOT_SITE_CODE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
