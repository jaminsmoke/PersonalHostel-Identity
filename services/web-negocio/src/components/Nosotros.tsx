import { fondoUrl } from "../media";
import { useWeb } from "../web-context";
import { SlotTexto } from "./SlotTexto";

export function Nosotros() {
  const web = useWeb();
  const perfil = web.perfil;
  const imagen = fondoUrl(web, "inicio");
  const hayCopy = Boolean(perfil?.eslogan || perfil?.descripcion);
  const hayLugar = Boolean(perfil?.direccion || perfil?.ciudad);
  const fotoPropia = web.fondos?.inicio?.fuente === "upload" || web.fondos?.inicio?.fuente === "hero";

  return (
    <section className="py-section-gap px-margin-mobile md:px-gutter max-w-page mx-auto">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-section-gap items-center">
        <div className="order-2 md:order-1 relative aspect-[4/5] rounded overflow-hidden">
          <img
            className="object-cover w-full h-full border border-outline-variant rounded"
            src={imagen}
            alt={fotoPropia ? web.nombre : ""}
            loading="lazy"
          />
        </div>
        <div className="order-1 md:order-2 flex flex-col gap-stack-lg">
          {perfil?.eslogan ? (
            <h2 className="font-display text-headline-lg-mobile md:text-headline-lg text-on-surface">
              {perfil.eslogan}
            </h2>
          ) : (
            <h2 className="font-display text-headline-lg-mobile md:text-headline-lg text-on-surface">
              {web.nombre}
            </h2>
          )}
          <div className="w-12 h-1 bg-primary-fixed-dim" />
          {perfil?.descripcion ? (
            <p className="text-body-lg text-on-surface-variant">{perfil.descripcion}</p>
          ) : (
            <SlotTexto lineas={3} />
          )}
          {hayLugar && (
            <p className="text-body-md text-on-surface-variant">
              {perfil?.direccion}
              {perfil?.direccion && perfil?.ciudad ? ", " : ""}
              {perfil?.ciudad}
            </p>
          )}
          {!hayCopy && !hayLugar && <div className="h-4" aria-hidden />}
        </div>
      </div>
    </section>
  );
}
