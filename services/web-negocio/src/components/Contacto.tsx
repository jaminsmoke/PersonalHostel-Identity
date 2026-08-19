import type { WebNegocio } from "../types";

export function Contacto({ web }: { web: WebNegocio }) {
  const c = web.contacto!;
  const hayDireccion = Boolean(web.perfil?.direccion || web.perfil?.ciudad);
  const redes = Object.entries(c.redes || {});

  return (
    <section
      id="contacto"
      className="py-section-gap px-margin-mobile md:px-gutter max-w-page mx-auto scroll-mt-20"
    >
      <h2 className="text-label-md text-primary-fixed-dim uppercase tracking-widest mb-stack-lg">
        Contacto
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-gutter">
        <div className="bg-surface rounded-xl p-stack-lg border border-outline-variant/40 flex flex-col gap-stack-md">
          {hayDireccion && (
            <div className="flex items-start gap-4">
              <span className="text-outline mt-1" aria-hidden>
                📍
              </span>
              <div>
                <span className="block text-label-md text-outline uppercase tracking-wider mb-1">
                  Dirección
                </span>
                <p className="text-body-md text-on-surface">
                  {web.perfil?.direccion}
                  {web.perfil?.direccion && web.perfil?.ciudad ? ", " : ""}
                  {web.perfil?.ciudad}
                </p>
              </div>
            </div>
          )}
          {c.telefono && (
            <div className="flex items-start gap-4">
              <span className="text-outline mt-1" aria-hidden>
                📞
              </span>
              <div>
                <span className="block text-label-md text-outline uppercase tracking-wider mb-1">
                  Teléfono
                </span>
                <a className="text-body-lg text-on-surface hover:text-primary transition-colors" href={`tel:${c.telefono}`}>
                  {c.telefono}
                </a>
              </div>
            </div>
          )}
          {c.email_contacto && (
            <div className="flex items-start gap-4">
              <span className="text-outline mt-1" aria-hidden>
                ✉️
              </span>
              <div>
                <span className="block text-label-md text-outline uppercase tracking-wider mb-1">
                  Email
                </span>
                <a
                  className="text-body-lg text-on-surface hover:text-primary transition-colors break-all"
                  href={`mailto:${c.email_contacto}`}
                >
                  {c.email_contacto}
                </a>
              </div>
            </div>
          )}
          {c.web && (
            <div className="flex items-start gap-4">
              <span className="text-outline mt-1" aria-hidden>
                🌐
              </span>
              <div>
                <span className="block text-label-md text-outline uppercase tracking-wider mb-1">
                  Web
                </span>
                <a
                  className="text-body-lg text-on-surface hover:text-primary transition-colors break-all"
                  href={c.web}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {c.web}
                </a>
              </div>
            </div>
          )}
          {redes.length > 0 && (
            <div className="flex gap-4 pt-stack-md border-t border-outline-variant/40">
              {redes.map(([nombre, url]) => (
                <a
                  key={nombre}
                  className="text-on-surface-variant hover:text-primary transition-colors text-label-md uppercase tracking-wider"
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {nombre}
                </a>
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}