import { absUrl } from "../config";
import type { WebNegocio } from "../types";

export function Equipo({ web }: { web: WebNegocio }) {
  return (
    <section
      id="equipo"
      className="py-section-gap px-margin-mobile md:px-gutter max-w-page mx-auto scroll-mt-20"
    >
      <h2 className="text-label-md text-primary-fixed-dim uppercase tracking-widest mb-stack-md">
        Equipo
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
        {web.equipo.map((m) => (
          <div
            key={m.camarero_id}
            className="flex flex-col bg-surface-variant rounded-lg border border-outline-variant/50 overflow-hidden"
          >
            {m.foto_url && (
              <img
                className="h-64 w-full object-cover"
                src={absUrl(m.foto_url)}
                alt={`${m.nombre} ${m.apellidos}`}
                loading="lazy"
              />
            )}
            <div className="p-6 flex flex-col gap-2">
              <h3 className="font-display text-headline-md text-on-surface">
                {m.nombre} {m.apellidos}
              </h3>
              {m.nick && (
                <p className="text-label-md text-primary uppercase tracking-wider">{m.nick}</p>
              )}
              <p className="text-label-md text-on-surface-variant uppercase tracking-wider">
                {m.rol}
              </p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}