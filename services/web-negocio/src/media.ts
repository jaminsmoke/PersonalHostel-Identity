import type { WebNegocio } from "./types";
import { absUrl } from "./config";
import { rutaNegocio } from "./web-context";

export const STUBS = {
  hero: "/stubs/hero.webp",
  nosotros: "/stubs/nosotros.webp",
  interior: "/stubs/interior.webp",
  mapa: "/stubs/mapa.webp",
  retrato: "/stubs/retrato.svg",
} as const;

export const FONDOS_DEFAULT = {
  inicio: "/stubs/fondos/estate-inicio-1.webp",
  horario: "/stubs/fondos/estate-horario-1.webp",
  carta: "/stubs/fondos/estate-carta-1.webp",
  equipo: "/stubs/fondos/estate-equipo-1.webp",
  contacto: "/stubs/fondos/estate-contacto-1.webp",
} as const;

export type FondoSlot = keyof typeof FONDOS_DEFAULT;

/** Foto real del local o cromado de plantilla (misma origen, sin CDN). */
export function mediaUrl(urlReal: string | null | undefined, stub: string): string {
  return absUrl(urlReal) ?? stub;
}

export function fondoUrl(web: WebNegocio, slot: FondoSlot): string {
  return mediaUrl(web.fondos?.[slot]?.url, FONDOS_DEFAULT[slot]);
}

export function urlPaginaPublica(slug: string, pagina?: string): string {
  const path = rutaNegocio(slug, pagina);
  if (typeof window === "undefined") return path;
  return `${window.location.origin}${path}`;
}
