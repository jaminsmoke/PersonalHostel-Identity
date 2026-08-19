import { useMemo, useState } from "react";
import { useWeb } from "../web-context";
import type { CategoriaCarta, ProductoPublico } from "../types";

function formatoPrecio(centimos: number, moneda: string): string {
  const simbolo = moneda === "EUR" ? "€" : moneda;
  return `${(centimos / 100).toFixed(2)} ${simbolo}`;
}

function agruparPorDestino(categorias: CategoriaCarta[], destino: "barra" | "cocina") {
  return categorias
    .map((cat) => ({
      ...cat,
      productos: cat.productos.filter((p) => p.destino === destino),
    }))
    .filter((cat) => cat.productos.length > 0);
}

function ListaCategorias({ categorias }: { categorias: CategoriaCarta[] }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-x-gutter gap-y-stack-lg">
      {categorias.map((cat) => (
        <section
          key={cat.nombre}
          className="bg-surface/60 backdrop-blur-xl p-6 md:p-8 rounded-lg border border-outline-variant/20"
        >
          <h2 className="font-display text-headline-md text-primary mb-stack-md border-b border-outline-variant/20 pb-4">
            {cat.nombre}
          </h2>
          <ul className="space-y-6">
            {cat.productos.map((p: ProductoPublico) => (
              <li key={p.nombre} className="flex justify-between items-baseline gap-4">
                <div className="flex-grow pr-4">
                  <h3 className="font-display text-body-lg text-on-surface">{p.nombre}</h3>
                  {p.descripcion && (
                    <p className="text-label-md text-on-surface-variant mt-1">{p.descripcion}</p>
                  )}
                </div>
                <div className="text-label-md text-primary whitespace-nowrap tabular-nums">
                  {formatoPrecio(p.precio_centimos, p.moneda)}
                </div>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

export function Carta() {
  const web = useWeb();
  const destinos = useMemo(() => {
    const set = new Set(web.categorias.flatMap((c) => c.productos.map((p) => p.destino)));
    return { barra: set.has("barra"), cocina: set.has("cocina") };
  }, [web.categorias]);
  const ambos = destinos.barra && destinos.cocina;
  const [tab, setTab] = useState<"cocina" | "barra">(destinos.cocina ? "cocina" : "barra");
  const categorias = ambos
    ? agruparPorDestino(web.categorias, tab)
    : destinos.cocina
      ? agruparPorDestino(web.categorias, "cocina")
      : destinos.barra
        ? agruparPorDestino(web.categorias, "barra")
        : web.categorias;

  return (
    <section className="flex-grow pt-[120px] pb-section-gap px-margin-mobile md:px-gutter max-w-page mx-auto w-full">
      <div className="text-center mb-stack-lg md:mb-section-gap">
        <h1 className="font-display text-headline-lg-mobile md:text-display-lg text-on-surface mb-stack-sm">
          La carta
        </h1>
        <p className="text-body-lg text-on-surface-variant max-w-2xl mx-auto">
          Selección de temporada, agrupada como en el local.
        </p>
      </div>
      {ambos && (
        <div className="flex justify-center border-b border-outline-variant/30 mb-stack-lg">
          <button
            type="button"
            onClick={() => setTab("cocina")}
            className={`px-8 py-4 text-label-md uppercase tracking-widest ${
              tab === "cocina"
                ? "text-primary border-b-2 border-primary"
                : "text-on-surface-variant hover:text-primary"
            }`}
          >
            Cocina
          </button>
          <button
            type="button"
            onClick={() => setTab("barra")}
            className={`px-8 py-4 text-label-md uppercase tracking-widest ${
              tab === "barra"
                ? "text-primary border-b-2 border-primary"
                : "text-on-surface-variant hover:text-primary"
            }`}
          >
            Barra
          </button>
        </div>
      )}
      <ListaCategorias categorias={categorias} />
    </section>
  );
}
