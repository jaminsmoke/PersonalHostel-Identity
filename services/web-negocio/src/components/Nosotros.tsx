import { absUrl } from "../config";
import type { WebNegocio } from "../types";

export function Nosotros({ web }: { web: WebNegocio }) {
  const perfil = web.perfil!;
  const imagen = absUrl(web.hero?.url);

  return (
    <section id="nosotros" className="py-section-gap px-margin-mobile md:px-gutter max-w-page mx-auto scroll-mt-20">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-section-gap items-center">
        {imagen && (
          <div className="order-2 md:order-1 relative aspect-[4/5] rounded-xl overflow-hidden">
            <img
              className="object-cover w-full h-full border border-outline-variant rounded-xl"
              src={imagen}
              alt={web.nombre}
              loading="lazy"
            />
          </div>
        )}
        <div className="order-1 md:order-2 flex flex-col gap-stack-lg">
          {perfil.eslogan && (
            <h2 className="font-display text-headline-lg-mobile md:text-headline-lg text-on-surface">
              {perfil.eslogan}
            </h2>
          )}
          <div className="w-12 h-1 bg-primary-fixed-dim" />
          {perfil.descripcion && (
            <p className="text-body-lg text-on-surface-variant">{perfil.descripcion}</p>
          )}
          {(perfil.direccion || perfil.ciudad) && (
            <p className="text-body-md text-on-surface-variant">
              {perfil.direccion}
              {perfil.direccion && perfil.ciudad ? ", " : ""}
              {perfil.ciudad}
            </p>
          )}
        </div>
      </div>
    </section>
  );
}