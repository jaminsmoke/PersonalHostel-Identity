import { absUrl } from "../config";
import { useWeb } from "../web-context";

export function Nosotros() {
  const web = useWeb();
  const perfil = web.perfil;
  if (!perfil) return null;
  const imagen = absUrl(web.hero?.url);

  return (
    <section className="py-section-gap px-margin-mobile md:px-gutter max-w-page mx-auto">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-section-gap items-center">
        {imagen && (
          <div className="order-2 md:order-1 relative aspect-[4/5] rounded overflow-hidden">
            <img
              className="object-cover w-full h-full border border-outline-variant rounded"
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
