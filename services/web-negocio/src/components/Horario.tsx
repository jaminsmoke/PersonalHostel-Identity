import type { HorarioDia, WebNegocio } from "../types";

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

export function Horario({ web }: { web: WebNegocio }) {
  const grupos = agrupar(web.horario!);
  return (
    <section
      id="horario"
      className="py-section-gap px-margin-mobile md:px-gutter max-w-page mx-auto scroll-mt-20"
    >
      <h2 className="text-label-md text-primary-fixed-dim uppercase tracking-widest mb-stack-md">
        Horario
      </h2>
      <ul className="border-t border-outline-variant/40">
        {grupos.map((g, i) => (
          <li
            key={i}
            className="flex justify-between gap-4 py-stack-md border-b border-outline-variant/40 text-body-md"
          >
            <span className="font-semibold text-on-surface">
              {g.desde === g.hasta ? DIAS[g.desde] : `${DIAS[g.desde]} a ${DIAS[g.hasta]}`}
            </span>
            <span className="text-on-surface-variant tabular-nums">
              {g.cerrado
                ? "Cerrado"
                : g.turnos.map((t) => `${t.abre}–${t.cierra}`).join(" y ")}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}