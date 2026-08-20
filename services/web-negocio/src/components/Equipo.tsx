import { STUBS, mediaUrl } from "../media";
import { useWeb } from "../web-context";
import { FondoPagina } from "./FondoPagina";
import { SlotTexto } from "./SlotTexto";
import type { MiembroEquipo } from "../types";

function CardMiembro({ m }: { m: MiembroEquipo }) {
  const foto = mediaUrl(m.foto_url, STUBS.retrato);
  return (
    <article className="flex flex-col bg-surface-variant rounded border border-outline-variant/50 overflow-hidden transition-transform duration-300 hover:-translate-y-1">
      <img
        className="h-80 w-full object-cover"
        src={foto}
        alt={m.foto_url ? `${m.nombre} ${m.apellidos}` : ""}
        loading="lazy"
      />
      <div className="p-6 flex flex-col gap-2">
        <h3 className="font-display text-headline-md text-on-surface">
          {m.nombre} {m.apellidos}
        </h3>
        {m.nick && (
          <p className="text-label-md text-primary uppercase tracking-wider">{m.nick}</p>
        )}
        <p className="text-label-md text-primary-fixed-dim uppercase tracking-wider">{m.rol}</p>
        <SlotTexto lineas={3} className="mt-2" />
      </div>
    </article>
  );
}

function CardHueco() {
  return (
    <article className="flex flex-col bg-surface-variant rounded border border-outline-variant/50 overflow-hidden">
      <img className="h-80 w-full object-cover" src={STUBS.retrato} alt="" />
      <div className="p-6 flex flex-col gap-3">
        <div className="h-8 w-2/3 bg-outline-variant/25 rounded" />
        <div className="h-4 w-1/3 bg-outline-variant/20 rounded" />
        <SlotTexto lineas={3} className="mt-1" />
      </div>
    </article>
  );
}

export function Equipo() {
  const web = useWeb();
  const hayEquipo = web.equipo.length > 0;

  return (
    <section className="relative flex-grow min-h-[calc(100vh-5rem)] pt-32 pb-section-gap">
      <FondoPagina slot="equipo" />
      <div className="relative z-10 px-gutter max-w-page mx-auto w-full">
      <section className="mb-section-gap max-w-3xl">
        <h1 className="font-display text-headline-lg-mobile md:text-display-lg text-on-surface mb-stack-lg">
          El equipo
        </h1>
        <p className="text-body-lg text-on-surface-variant">
          {hayEquipo
            ? `Las personas de ${web.nombre} que el local ha elegido mostrar.`
            : "El equipo aún no se muestra."}
        </p>
      </section>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
        {hayEquipo
          ? web.equipo.map((m) => <CardMiembro key={m.camarero_id} m={m} />)
          : [0, 1, 2].map((i) => <CardHueco key={i} />)}
      </div>
      </div>
    </section>
  );
}
