declare global {
  interface Window {
    NEGOCIO_API_URL?: string;
  }
}

const base = (window.NEGOCIO_API_URL || "http://localhost:8082").replace(/\/+$/, "");

export const API_BASE = base;

export function absUrl(url: string | null | undefined): string | undefined {
  if (!url) return undefined;
  return /^https?:\/\//.test(url) ? url : `${base}${url}`;
}