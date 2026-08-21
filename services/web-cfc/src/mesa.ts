export type Destino = "barra" | "cocina";

export type Producto = {
  id: string;
  nombre: string;
  precio_centimos: number;
  categoria: string;
  destino: Destino;
};

export type Linea = {
  productoId: string;
  nombre: string;
  cantidad: number;
  precio_centimos: number;
  nota?: string;
};

export type MesaSesion = {
  token: string;
  etiqueta: string;
  localNombre: string;
  carta: Producto[];
  cuenta: Linea[];
  modo: "demo" | "ok" | "pendiente_contrato";
};

/** Catálogo local solo para el token `demo`. No simula aceptación de Bar. */
export const CARTA_DEMO: Producto[] = [
  {
    id: "cafe-leche",
    nombre: "Café con leche",
    precio_centimos: 150,
    categoria: "Cafés",
    destino: "barra",
  },
  {
    id: "cafe-solo",
    nombre: "Café solo",
    precio_centimos: 130,
    categoria: "Cafés",
    destino: "barra",
  },
  {
    id: "cana",
    nombre: "Caña",
    precio_centimos: 200,
    categoria: "Cervezas",
    destino: "barra",
  },
  {
    id: "tarta",
    nombre: "Tarta de queso",
    precio_centimos: 450,
    categoria: "Postres",
    destino: "cocina",
  },
  {
    id: "croquetas",
    nombre: "Croquetas",
    precio_centimos: 700,
    categoria: "Raciones",
    destino: "cocina",
  },
];

export function cargarMesa(token: string): MesaSesion {
  const limpio = token.trim();
  if (limpio === "demo") {
    return {
      token: limpio,
      etiqueta: "B1",
      localNombre: "Demostración",
      carta: CARTA_DEMO,
      cuenta: [],
      modo: "demo",
    };
  }
  return {
    token: limpio,
    etiqueta: "Tu mesa",
    localNombre: "",
    carta: [],
    cuenta: [],
    modo: "pendiente_contrato",
  };
}

export function euros(centimos: number): string {
  return (centimos / 100).toLocaleString("es-ES", {
    style: "currency",
    currency: "EUR",
  });
}

export function totalLineas(lineas: Linea[]): number {
  return lineas.reduce(
    (acc, linea) => acc + linea.precio_centimos * linea.cantidad,
    0,
  );
}
