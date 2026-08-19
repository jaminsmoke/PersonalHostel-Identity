import { createContext, useContext } from "react";
import type { WebNegocio } from "./types";

export const WebContext = createContext<WebNegocio | null>(null);

export function useWeb(): WebNegocio {
  const web = useContext(WebContext);
  if (!web) {
    throw new Error("useWeb debe usarse dentro de WebLayout");
  }
  return web;
}

export function rutaNegocio(slug: string, pagina?: string): string {
  const base = `/negocios/${slug}`;
  return pagina ? `${base}/${pagina}` : base;
}
