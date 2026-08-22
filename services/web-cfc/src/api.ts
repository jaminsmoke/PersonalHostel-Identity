import { API_BASE } from "./config";
import { cargarMesa, type Linea, type MesaSesion, type Producto } from "./mesa";

export type MesaResolveError = {
  tipo: "invalido" | "revocado" | "red";
};

export type PedidoError = {
  tipo: "cerrado" | "limite" | "red";
};

type MesaPublica = {
  establecimiento_id: string;
  establecimiento_nombre: string;
  mesa_uuid: string;
  etiqueta: string;
  admite_pedidos?: boolean;
  bar_en_linea?: boolean;
};

type CartaPublica = {
  productos: Array<{
    id: string;
    nombre: string;
    precio_centimos: number;
    categoria: string;
    destino: "barra" | "cocina";
  }>;
  admite_pedidos: boolean;
  bar_en_linea: boolean;
};

type CuentaPublica = {
  lineas: Array<{
    producto_id: string;
    nombre: string;
    cantidad: number;
    precio_centimos: number;
  }>;
};

function errorMesa(status: number): MesaResolveError {
  if (status === 404) return { tipo: "invalido" };
  if (status === 410) return { tipo: "revocado" };
  return { tipo: "red" };
}

export function esErrorPedido(err: unknown): err is PedidoError {
  return (
    typeof err === "object" &&
    err !== null &&
    "tipo" in err &&
    (err.tipo === "cerrado" || err.tipo === "limite" || err.tipo === "red")
  );
}

export async function resolverMesa(token: string): Promise<MesaSesion> {
  const limpio = token.trim();
  if (limpio === "demo") {
    return cargarMesa("demo");
  }
  const resp = await fetch(
    `${API_BASE}/v1/cfc/mesa/${encodeURIComponent(limpio)}`,
  );
  if (!resp.ok) {
    throw errorMesa(resp.status);
  }
  const body = (await resp.json()) as MesaPublica;
  const [carta, cuenta] = await Promise.all([
    cargarCarta(limpio),
    cargarCuenta(limpio),
  ]);
  return {
    token: limpio,
    etiqueta: body.etiqueta,
    localNombre: body.establecimiento_nombre,
    carta: carta.productos,
    cuenta: cuenta.lineas,
    admitePedidos: carta.admite_pedidos,
    barEnLinea: carta.bar_en_linea,
    modo: "ok",
  };
}

export async function cargarCarta(token: string): Promise<{
  productos: Producto[];
  admite_pedidos: boolean;
  bar_en_linea: boolean;
}> {
  const resp = await fetch(
    `${API_BASE}/v1/cfc/mesa/${encodeURIComponent(token)}/carta`,
  );
  if (!resp.ok) {
    throw errorMesa(resp.status);
  }
  const body = (await resp.json()) as CartaPublica;
  return {
    admite_pedidos: body.admite_pedidos,
    bar_en_linea: body.bar_en_linea,
    productos: body.productos.map((p) => ({
      id: p.id,
      nombre: p.nombre,
      precio_centimos: p.precio_centimos,
      categoria: p.categoria,
      destino: p.destino,
    })),
  };
}

export async function cargarCuenta(token: string): Promise<{ lineas: Linea[] }> {
  const resp = await fetch(
    `${API_BASE}/v1/cfc/mesa/${encodeURIComponent(token)}/cuenta`,
  );
  if (!resp.ok) {
    throw errorMesa(resp.status);
  }
  const body = (await resp.json()) as CuentaPublica;
  return { lineas: body.lineas.map(lineaCuenta) };
}

export async function enviarPedidoMesa(
  token: string,
  lineas: Linea[],
): Promise<void> {
  const resp = await fetch(
    `${API_BASE}/v1/cfc/mesa/${encodeURIComponent(token)}/pedidos`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        idempotency_key: crypto.randomUUID(),
        lineas: lineas.map((l) => ({
          producto_id: l.productoId,
          cantidad: l.cantidad,
        })),
      }),
    },
  );
  if (resp.status === 409) {
    const err: PedidoError = { tipo: "cerrado" };
    throw err;
  }
  if (resp.status === 429) {
    const err: PedidoError = { tipo: "limite" };
    throw err;
  }
  if (!resp.ok) {
    const err: PedidoError = { tipo: "red" };
    throw err;
  }
}

function lineaCuenta(linea: CuentaPublica["lineas"][number]): Linea {
  return {
    productoId: linea.producto_id,
    nombre: linea.nombre,
    cantidad: linea.cantidad,
    precio_centimos: linea.precio_centimos,
  };
}
