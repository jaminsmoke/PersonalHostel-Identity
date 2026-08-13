import type { KanbanConfig } from "./config"

/**
 * Shared test fixture: a full, valid KanbanConfig with stable IDs.
 * Used across unit test files to avoid duplication.
 */
export function makeConfig(): KanbanConfig {
  return {
    projectId: "PVT_proj",
    repoId: "R_repo",
    repo: "jaminsmoke/jarvis-skills",
    fields: {
      Status: "F_status",
      "Versión": "F_version",
      Prioridad: "F_priority",
      Decision: "F_decision",
      Tipo: "F_tipo",
      "Área principal": "F_area",
      HighLighted: "F_hl",
      "Inicio exacto": "F_ie",
      "Inicio": "F_i",
    },
    options: {
      status: {
        Detectado: "O_detectado",
        Debate: "O_debate",
        Roadmap: "O_roadmap",
        Ejecutando: "O_ejec",
        Verificando: "O_verif",
        Changelog: "O_chg",
      },
      version: { "Sin asignar": "O_sa", "v0.1.0": "O_v010" },
      priority: { Alta: "O_alta", Media: "O_media", Baja: "O_baja" },
      decision: { Pendiente: "O_pend", Aprobado: "O_aprobado", Diferido: "O_dif", Cancelado: "O_canc" },
      tipo: { Bug: "O_bug", Feature: "O_feature", Maintenance: "O_maint" },
      area: { "kanban-cli": "O_kc", Docs: "O_docs" },
      highlighted: { Yes: "O_yes", No: "O_no" },
    },
  }
}
