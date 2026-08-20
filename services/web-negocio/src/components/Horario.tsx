import type { HorarioDia } from "../types";
import { FondoPagina } from "./FondoPagina";
import { IconoInfo } from "../icons";
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
  const publicado = Boolean(web.horario?.length);

  return (
    <section className="relative min-h-[calc(100vh-5rem)] pt-20">
      <FondoPagina slot="horario" />
      <div className="relative z-10 max-w-page mx-auto px-gutter py-section-gap flex flex-col items-center">
        <div className="text-center mb-stack-lg">
          <h1 className="font-display text-headline-lg-mobile md:text-display-lg text-primary mb-stack-sm">
            Horario
          </h1>
          <p className="text-body-lg text-on-surface-variant max-w-2xl mx-auto">
            {web.nombre}
          </p>
        </div>
        <div className="w-full max-w-2xl glass-panel p-stack-lg md:p-12">
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
          {!publicado && (
            <p className="flex items-center justify-center gap-2 text-center text-body-md text-on-surface-variant mb-stack-lg">
              <IconoInfo className="w-5 h-5 text-primary shrink-0" />
              Aún no hemos publicado el horario.
            </p>
          )}
          <ul>
            {publicado
              ? grupos.map((g, i) => (
                  <li
                    key={i}
                    className="flex justify-between items-center py-stack-md border-b border-outline-variant/30 px-4 hover:bg-surface/40 transition-colors"
                  >
                    <span className="font-display text-headline-sm text-on-surface">
                      {g.desde === g.hasta ? DIAS[g.desde] : `${DIAS[g.desde]} a ${DIAS[g.hasta]}`}
                    </span>
                    <span className="block text-label-md text-primary tabular-nums text-right">
                      {g.cerrado
                        ? "Cerrado"
                        : g.turnos.map((t) => `${t.abre}–${t.cierra}`).join(" y ")}
                    </span>
                  </li>
                ))
              : DIAS.map((dia) => (
                  <li
                    key={dia}
                    className="flex justify-between items-center py-stack-md border-b border-outline-variant/30 px-4"
                  >
                    <span className="font-display text-headline-sm text-on-surface">{dia}</span>
                    <span className="block text-label-md text-outline tabular-nums" aria-hidden>
                      —
                    </span>
                  </li>
                ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
