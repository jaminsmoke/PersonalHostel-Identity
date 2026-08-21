import { API_BASE } from "./config";
import { cargarMesa, type MesaSesion } from "./mesa";

export type MesaResolveError = {
  tipo: "invalido" | "revocado" | "red";
};

type MesaPublica = {
  establecimiento_id: string;
  establecimiento_nombre: string;
  mesa_uuid: string;
  etiqueta: string;
};

export async function resolverMesa(token: string): Promise<MesaSesion> {
  const limpio = token.trim();
  if (limpio === "demo") {
    return cargarMesa("demo");
  }
  const resp = await fetch(
    `${API_BASE}/v1/cfc/mesa/${encodeURIComponent(limpio)}`,
  );
  if (resp.status === 404) {
    const err: MesaResolveError = { tipo: "invalido" };
    throw err;
  }
  if (resp.status === 410) {
    const err: MesaResolveError = { tipo: "revocado" };
    throw err;
  }
  if (!resp.ok) {
    const err: MesaResolveError = { tipo: "red" };
    throw err;
  }
  const body = (await resp.json()) as MesaPublica;
  return {
    token: limpio,
    etiqueta: body.etiqueta,
    localNombre: body.establecimiento_nombre,
    carta: [],
    cuenta: [],
    modo: "ok",
  };
}
