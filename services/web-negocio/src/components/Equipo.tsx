import { absUrl } from "../config";
import { useWeb } from "../web-context";

export function Equipo() {
  const web = useWeb();
  return (
    <section className="flex-grow pt-32 pb-section-gap px-gutter max-w-page mx-auto w-full">
      <section className="mb-section-gap max-w-3xl">
        <h1 className="font-display text-headline-lg-mobile md:text-display-lg text-on-surface mb-stack-lg">
          El equipo
        </h1>
        <p className="text-body-lg text-on-surface-variant">
          Las personas de {web.nombre} que el local ha elegido mostrar.
        </p>
      </section>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
        {web.equipo.map((m) => (
          <div
            key={m.camarero_id}
            className="flex flex-col bg-surface-variant rounded border border-outline-variant/50 overflow-hidden"
          >
            {m.foto_url && (
              <img
                className="h-80 w-full object-cover"
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
              <p className="text-label-md text-on-surface-variant uppercase tracking-wider">{m.rol}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
