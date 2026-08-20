import { useEffect, useRef, useCallback } from "react";
import { cargarWeb } from "./api";
import type { WebNegocio } from "./types";

/**
 * Hook que mantiene los datos de la web públicos frescos:
 * - Refetch al volver a la pestaña (visibilitychange → visible)
 * - Polling periódico cada [intervalMs] ms (para kioscos/tablets fijas)
 * - Usa ETag/304 para evitar re-renders innecesarios
 *
 * @param slug - Slug del establecimiento
 * @param intervalMs - Intervalo de polling en ms (default: 60 000)
 * @param onActualiza - Callback cuando llegan datos nuevos
 */
export function useRefetch(
  slug: string,
  intervalMs: number = 60_000,
  onActualiza: (web: WebNegocio) => void,
) {
  const etagRef = useRef<string>("");
  const activoRef = useRef(true);

  const refetch = useCallback(async () => {
    if (!slug) return;
    try {
      const resultado = await cargarWeb(slug, etagRef.current || undefined);
      if (!activoRef.current) return;
      if (resultado) {
        etagRef.current = resultado.etag;
        onActualiza(resultado.web);
      }
      // 304 → sin cambios, no se actualiza state
    } catch {
      // Error de red: se ignora silenciosamente; el dato anterior sigue vigente
    }
  }, [slug, onActualiza]);

  // Refetch al volver a la pestaña
  useEffect(() => {
    const handler = () => {
      if (document.visibilityState === "visible") refetch();
    };
    document.addEventListener("visibilitychange", handler);
    return () => document.removeEventListener("visibilitychange", handler);
  }, [refetch]);

  // Polling periódico
  useEffect(() => {
    activoRef.current = true;
    const id = setInterval(refetch, intervalMs);
    return () => {
      activoRef.current = false;
      clearInterval(id);
    };
  }, [refetch, intervalMs]);
}
