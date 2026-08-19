import type { WebNegocio } from "../types";

function formatoPrecio(centimos: number, moneda: string): string {
  const simbolo = moneda === "EUR" ? "€" : moneda;
  return `${(centimos / 100).toFixed(2)} ${simbolo}`;
}

export function Carta({ web }: { web: WebNegocio }) {
  return (
    <section
      id="carta"
      className="py-section-gap px-margin-mobile md:px-gutter max-w-page mx-auto scroll-mt-20"
    >
      <h2 className="text-label-md text-primary-fixed-dim uppercase tracking-widest mb-stack-md">
        Carta
      </h2>
      {web.categorias.map((cat) => (
        <div key={cat.nombre} className="mb-stack-lg">
          <h3 className="font-display text-headline-sm text-on-surface mb-stack-sm">{cat.nombre}</h3>
          <ul className="border-t border-outline-variant/40">
            {cat.productos.map((p) => (
              <li
                key={p.nombre}
                className="flex justify-between gap-4 py-stack-sm border-b border-outline-variant/40 text-body-md"
              >
                <span className="text-on-surface">{p.nombre}</span>
                <span className="text-on-surface-variant tabular-nums whitespace-nowrap">
                  {formatoPrecio(p.precio_centimos, p.moneda)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  );
}