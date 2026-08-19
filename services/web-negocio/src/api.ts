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

export async function cargarWeb(slug: string): Promise<WebNegocio> {
  const url = `${API_BASE}/v1/negocio/web?slug=${encodeURIComponent(slug)}`;
  const res = await fetch(url, { headers: { Accept: "application/json" } });
  const body: Partial<ErrorWeb> & Partial<WebNegocio> = await res
    .json()
    .catch(() => ({}));
  if (!res.ok) {
    throw new ErrorPublico(res.status, body.code || "", body.detail || "Error");
  }
  return body as WebNegocio;
}