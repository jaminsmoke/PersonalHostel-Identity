import { Link, useParams } from "react-router-dom";
import { absUrl } from "../config";
import { rutaNegocio, useWeb } from "../web-context";

export function Hero() {
  const web = useWeb();
  const { slug } = useParams<{ slug: string }>();
  const heroUrl = absUrl(web.hero?.url);
  const abierto = web.abierto_ahora;
  const hayCarta = web.categorias.length > 0;
  const hayContacto = Boolean(web.contacto);
  if (!slug) return null;

  return (
    <section id="inicio" className="relative min-h-screen flex items-center justify-center pt-20">
      <div className="absolute inset-0 z-0">
        {heroUrl ? (
          <div
            className="w-full h-full bg-cover bg-center opacity-60"
            style={{ backgroundImage: `url(${heroUrl})` }}
            aria-hidden
          />
        ) : (
          <div className="w-full h-full bg-gradient-to-b from-surface-high to-background" />
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-background via-background/80 to-transparent" />
      </div>

      <div className="relative z-10 flex flex-col items-center text-center px-margin-mobile max-w-3xl mx-auto gap-stack-lg">
        {abierto && (
          <div className="inline-flex items-center gap-2 bg-surface-high/80 backdrop-blur px-4 py-2 rounded-full border border-outline-variant/40">
            <span
              className={`w-2 h-2 rounded-full ${abierto.abierto ? "bg-success animate-pulse" : "bg-danger"}`}
            />
            <span className="text-label-md text-on-surface uppercase tracking-widest">
              {abierto.abierto ? "Abierto ahora" : "Cerrado ahora"}
            </span>
          </div>
        )}

        <div>
          {web.perfil?.eslogan && (
            <p className="text-label-md text-primary-fixed-dim uppercase tracking-widest mb-2">
              {web.perfil.eslogan}
            </p>
          )}
          <h1 className="font-display text-display-lg text-inverse-surface mb-4 hidden md:block">
            {web.nombre}
          </h1>
          <h1 className="font-display text-headline-lg-mobile text-inverse-surface mb-4 md:hidden">
            {web.nombre}
          </h1>
          {web.tipo_establecimiento && (
            <p className="text-body-lg text-on-surface-variant capitalize">{web.tipo_establecimiento}</p>
          )}
        </div>

        <div className="flex flex-col sm:flex-row gap-stack-md mt-2 w-full sm:w-auto">
          {hayCarta && (
            <Link
              to={rutaNegocio(slug, "carta")}
              className="bg-primary-container text-on-primary-container text-label-md px-8 py-4 rounded hover:bg-primary transition-colors text-center uppercase tracking-widest"
            >
              Ver carta
            </Link>
          )}
          {hayContacto && (
            <Link
              to={rutaNegocio(slug, "contacto")}
              className="bg-surface-high text-on-surface border border-outline-variant text-label-md px-8 py-4 rounded hover:bg-surface-variant transition-colors text-center uppercase tracking-widest"
            >
              Cómo llegar
            </Link>
          )}
        </div>
      </div>
    </section>
  );
}
