import { useWeb } from "../web-context";

export function Contacto() {
  const web = useWeb();
  const c = web.contacto;
  const hayDireccion = Boolean(web.perfil?.direccion || web.perfil?.ciudad);
  const redes = Object.entries(c?.redes || {});
  const direccion = [web.perfil?.direccion, web.perfil?.ciudad].filter(Boolean).join(", ");

  return (
    <section className="flex-grow pt-[120px] pb-section-gap px-gutter max-w-page mx-auto w-full">
      <header className="mb-section-gap text-center md:text-left">
        <h1 className="font-display text-headline-lg-mobile md:text-display-lg text-primary mb-stack-md">
          Dónde estamos
        </h1>
        {web.perfil?.descripcion && (
          <p className="text-body-lg text-on-surface-variant max-w-2xl">{web.perfil.descripcion}</p>
        )}
      </header>
      <div className="grid grid-cols-1 md:grid-cols-12 gap-gutter">
        <div className="md:col-span-8 bg-surface-high rounded-xl overflow-hidden border border-outline-variant/20 relative min-h-[400px] grid place-items-center">
          <div className="absolute inset-0 bg-gradient-to-br from-surface-high to-surface-lowest" />
          <p className="relative z-10 text-label-md uppercase tracking-widest text-on-surface-variant">
            Mapa
          </p>
          {direccion && (
            <div className="absolute bottom-stack-lg left-stack-lg right-stack-lg">
              <h3 className="font-display text-headline-sm text-primary mb-1">{web.nombre}</h3>
              <p className="text-body-md text-on-surface">{direccion}</p>
            </div>
          )}
        </div>
        <div className="md:col-span-4 bg-surface rounded-xl p-stack-lg border border-outline-variant/20 flex flex-col gap-stack-md">
          <h2 className="font-display text-headline-md text-on-surface mb-stack-md">Contacto</h2>
          {hayDireccion && (
            <div>
              <span className="block text-label-md text-outline uppercase tracking-wider mb-1">
                Dirección
              </span>
              <p className="text-body-md text-on-surface">{direccion}</p>
            </div>
          )}
          {c?.telefono && (
            <div>
              <span className="block text-label-md text-outline uppercase tracking-wider mb-1">
                Teléfono
              </span>
              <a className="text-body-lg text-on-surface hover:text-primary" href={`tel:${c.telefono}`}>
                {c.telefono}
              </a>
            </div>
          )}
          {c?.email_contacto && (
            <div>
              <span className="block text-label-md text-outline uppercase tracking-wider mb-1">
                Email
              </span>
              <a
                className="text-body-lg text-on-surface hover:text-primary break-all"
                href={`mailto:${c.email_contacto}`}
              >
                {c.email_contacto}
              </a>
            </div>
          )}
          {c?.web && (
            <div>
              <span className="block text-label-md text-outline uppercase tracking-wider mb-1">Web</span>
              <a
                className="text-body-lg text-on-surface hover:text-primary break-all"
                href={c.web}
                target="_blank"
                rel="noopener noreferrer"
              >
                {c.web}
              </a>
            </div>
          )}
          {redes.length > 0 && (
            <div className="pt-stack-md border-t border-outline-variant/20 flex gap-4">
              {redes.map(([nombre, url]) => (
                <a
                  key={nombre}
                  className="text-on-surface-variant hover:text-primary text-label-md uppercase tracking-wider"
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
