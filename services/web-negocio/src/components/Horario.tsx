import type { HorarioDia } from "../types";
import { absUrl } from "../config";
import { useWeb } from "../web-context";

const DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];

interface Grupo {
  firma: string;
  desde: number;
  hasta: number;
  cerrado: boolean;
  turnos: HorarioDia["turnos"];
}

function firma(dia: HorarioDia): string {
  return dia.cerrado ? "cerrado" : JSON.stringify(dia.turnos || []);
}

function agrupar(horario: HorarioDia[]): Grupo[] {
  const grupos: Grupo[] = [];
  for (const dia of horario) {
    const f = firma(dia);
    const ultimo = grupos[grupos.length - 1];
    if (ultimo && ultimo.firma === f) {
      ultimo.hasta = dia.dia_semana;
    } else {
      grupos.push({
        firma: f,
        desde: dia.dia_semana,
        hasta: dia.dia_semana,
        cerrado: dia.cerrado,
        turnos: dia.turnos || [],
      });
    }
  }
  return grupos;
}

export function Horario() {
  const web = useWeb();
  const grupos = agrupar(web.horario || []);
  const abierto = web.abierto_ahora;
  const heroUrl = absUrl(web.hero?.url);

  return (
    <section className="relative min-h-[calc(100vh-5rem)] pt-20">
      <div className="absolute inset-0 z-0">
        {heroUrl ? (
          <div
            className="w-full h-full bg-cover bg-center"
            style={{ backgroundImage: `url(${heroUrl})` }}
            aria-hidden
          />
        ) : (
          <div className="w-full h-full bg-surface-high" />
        )}
        <div className="absolute inset-0 bg-background/85" />
      </div>
      <div className="relative z-10 max-w-page mx-auto px-gutter py-section-gap flex flex-col items-center">
        <div className="text-center mb-stack-lg">
          <h1 className="font-display text-headline-lg-mobile md:text-display-lg text-primary mb-stack-sm">
            Horario
          </h1>
          <p className="text-body-lg text-on-surface-variant max-w-2xl mx-auto">
            Te esperamos en {web.nombre}.
          </p>
        </div>
        <div className="w-full max-w-2xl bg-surface-high/90 backdrop-blur-sm border border-outline-variant rounded-lg p-stack-lg md:p-12">
          {!web.horario?.length ? (
            <p className="text-center text-body-lg text-on-surface-variant">
              Aún no hemos publicado el horario. Pregúntanos al local o vuelve más tarde.
            </p>
          ) : (
            <>
              {abierto && (
                <div className="flex justify-center mb-stack-lg">
                  <div
                    className={`inline-flex items-center gap-2 px-4 py-2 rounded-full border ${
                      abierto.abierto
                        ? "bg-[#1b5e20]/20 text-[#a5d6a7] border-[#1b5e20]"
                        : "bg-danger/10 text-danger border-danger/40"
                    }`}
                  >
                    <div
                      className={`w-2 h-2 rounded-full ${abierto.abierto ? "bg-[#81c784] animate-pulse" : "bg-danger"}`}
                    />
                    <span className="text-label-md uppercase tracking-wider">
                      {abierto.abierto ? "Abierto ahora" : "Cerrado ahora"}
                    </span>
                  </div>
                </div>
              )}
              <ul>
                {grupos.map((g, i) => (
                  <li
                    key={i}
                    className="flex justify-between items-center py-stack-md border-b border-outline-variant/30 px-4"
                  >
                    <span className="font-display text-headline-sm text-on-surface">
                      {g.desde === g.hasta ? DIAS[g.desde] : `${DIAS[g.desde]} a ${DIAS[g.hasta]}`}
                    </span>
                    <span className="text-right">
                      <span className="block text-label-md text-primary tabular-nums">
                        {g.cerrado
                          ? "Cerrado"
                          : g.turnos.map((t) => `${t.abre}–${t.cierra}`).join(" y ")}
                      </span>
                    </span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      </div>
    </section>
  );
}
