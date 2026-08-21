declare global {
  interface Window {
    NEGOCIO_API_URL?: string;
  }
}

const base = (window.NEGOCIO_API_URL || "http://localhost:8082").replace(
  /\/+$/,
  "",
);

export const API_BASE = base;
