import { absUrl } from "./config";
import { rutaNegocio } from "./web-context";

export const STUBS = {
  hero: "/stubs/hero.webp",
  nosotros: "/stubs/nosotros.webp",
  interior: "/stubs/interior.webp",
  mapa: "/stubs/mapa.webp",
  retrato: "/stubs/retrato.svg",
} as const;

/** Foto real del local o cromado de plantilla (misma origen, sin CDN). */
export function mediaUrl(urlReal: string | null | undefined, stub: string): string {
  return absUrl(urlReal) ?? stub;
}

export function urlPaginaPublica(slug: string, pagina?: string): string {
  const path = rutaNegocio(slug, pagina);
  if (typeof window === "undefined") return path;
  return `${window.location.origin}${path}`;
}
