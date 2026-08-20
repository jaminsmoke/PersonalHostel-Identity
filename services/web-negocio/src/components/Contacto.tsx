import { STUBS } from "../media";
import { IconoCorreo, IconoDirecciones, IconoPin, IconoTelefono, IconoWeb } from "../icons";
import { useWeb } from "../web-context";
import { FondoPagina } from "./FondoPagina";

export function Contacto() {
  const web = useWeb();
  const c = web.contacto;
  const redes = Object.entries(c?.redes || {});
  const direccion = [web.perfil?.direccion, web.perfil?.ciudad].filter(Boolean).join(", ");
  const mapsHref = direccion
    ? `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(direccion)}`
    : null;

  return (
    <section className="relative flex-grow min-h-[calc(100vh-5rem)] pt-[120px] pb-section-gap">
      <FondoPagina slot="contacto" />
      <div className="relative z-10 px-gutter max-w-page mx-auto w-full">
      <header className="mb-section-gap text-center md:text-left">
        <h1 className="font-display text-headline-lg-mobile md:text-display-lg text-primary mb-stack-md">
          Dónde estamos
        </h1>
        {web.perfil?.descripcion ? (
          <p className="text-body-lg text-on-surface-variant max-w-2xl">{web.perfil.descripcion}</p>
        ) : (
          <p className="text-body-lg text-on-surface-variant max-w-2xl">{web.nombre}</p>
        )}
      </header>
      <div className="grid grid-cols-1 md:grid-cols-12 gap-gutter">
        <div className="md:col-span-8 bg-surface-high rounded-xl overflow-hidden border border-outline-variant/20 relative min-h-[400px]">
          <img
            src={STUBS.mapa}
            alt=""
            className="absolute inset-0 w-full h-full object-cover mix-blend-luminosity opacity-80"
          />
          <div className="absolute inset-0 bg-background/40" />
          <div className="absolute inset-0 grid place-items-center pointer-events-none">
            <IconoPin className="w-12 h-12 text-primary drop-shadow-lg" />
          </div>
          {mapsHref ? (
            <a
              href={mapsHref}
              target="_blank"
              rel="noopener noreferrer"
              className="absolute top-stack-lg right-stack-lg z-10 bg-primary-container text-on-primary-container p-3 rounded shadow-lg hover:opacity-90"
              aria-label="Cómo llegar"
            >
              <IconoDirecciones className="w-6 h-6" />
            </a>
          ) : (
            <span
              className="absolute top-stack-lg right-stack-lg z-10 bg-surface-high text-outline p-3 rounded border border-outline-variant/40"
              aria-hidden
            >
              <IconoDirecciones className="w-6 h-6" />
            </span>
          )}
          <div className="absolute bottom-stack-lg left-stack-lg right-stack-lg z-10">
            <h3 className="font-display text-headline-sm text-primary mb-1">{web.nombre}</h3>
            {direccion ? (
              <p className="text-body-md text-on-surface">{direccion}</p>
            ) : (
              <p className="text-body-md text-on-surface-variant">Aún no hemos publicado la dirección.</p>
            )}
          </div>
        </div>
        <div className="md:col-span-4 glass-panel p-stack-lg flex flex-col gap-stack-md">
          <h2 className="font-display text-headline-md text-on-surface mb-stack-md">Contacto</h2>
          <div className="flex gap-3 items-start">
            <IconoPin className="w-5 h-5 text-primary mt-1 shrink-0" />
            <div>
              <span className="block text-label-md text-outline uppercase tracking-wider mb-1">
                Dirección
              </span>
              <p className="text-body-md text-on-surface">
                {direccion || "—"}
              </p>
            </div>
          </div>
          <div className="flex gap-3 items-start">
            <IconoTelefono className="w-5 h-5 text-primary mt-1 shrink-0" />
            <div>
              <span className="block text-label-md text-outline uppercase tracking-wider mb-1">
                Teléfono
              </span>
              {c?.telefono ? (
                <a className="text-body-lg text-on-surface hover:text-primary" href={`tel:${c.telefono}`}>
                  {c.telefono}
                </a>
              ) : (
                <p className="text-body-md text-on-surface-variant">—</p>
              )}
            </div>
          </div>
          <div className="flex gap-3 items-start">
            <IconoCorreo className="w-5 h-5 text-primary mt-1 shrink-0" />
            <div>
              <span className="block text-label-md text-outline uppercase tracking-wider mb-1">Email</span>
              {c?.email_contacto ? (
                <a
                  className="text-body-lg text-on-surface hover:text-primary break-all"
                  href={`mailto:${c.email_contacto}`}
                >
                  {c.email_contacto}
                </a>
              ) : (
                <p className="text-body-md text-on-surface-variant">—</p>
              )}
            </div>
          </div>
          <div className="flex gap-3 items-start">
            <IconoWeb className="w-5 h-5 text-primary mt-1 shrink-0" />
            <div>
              <span className="block text-label-md text-outline uppercase tracking-wider mb-1">Web</span>
              {c?.web ? (
                <a
                  className="text-body-lg text-on-surface hover:text-primary break-all"
                  href={c.web}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {c.web}
                </a>
              ) : (
                <p className="text-body-md text-on-surface-variant">—</p>
              )}
            </div>
          </div>
          {redes.length > 0 && (
            <div className="pt-stack-md border-t border-outline-variant/20 flex gap-4 flex-wrap">
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
      </div>
    </section>
  );
}
