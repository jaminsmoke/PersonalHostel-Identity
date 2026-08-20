import { API_BASE } from "./config";
import type { ErrorWeb, WebNegocio } from "./types";

export class ErrorPublico extends Error {
  status: number;
  code: string;
  constructor(status: number, code: string, detail: string) {
    super(detail);
    this.status = status;
    this.code = code;
  }
}

export interface ResultadoWeb {
  web: WebNegocio;
  etag: string;
}

/**
 * Carga la web del negocio. Si se pasa [etag], envía If-None-Match;
 * si el servidor responde 304, devuelve null (sin cambios).
 */
export async function cargarWeb(
  slug: string,
  etag?: string,
): Promise<ResultadoWeb | null> {
  const url = `${API_BASE}/v1/negocio/web?slug=${encodeURIComponent(slug)}`;
  const headers: Record<string, string> = { Accept: "application/json" };
  if (etag) headers["If-None-Match"] = etag;
  const res = await fetch(url, { headers });
  if (res.status === 304) return null;
  const body: Partial<ErrorWeb> & Partial<WebNegocio> = await res
    .json()
    .catch(() => ({}));
  if (!res.ok) {
    throw new ErrorPublico(res.status, body.code || "", body.detail || "Error");
  }
  return { web: body as WebNegocio, etag: res.headers.get("etag") || "" };
}