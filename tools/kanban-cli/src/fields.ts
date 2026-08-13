import type { KanbanConfig } from "./config"

/**
 * All field and option IDs resolved from the loaded config.
 * Provides type-safe access to execute mutations without hardcoding IDs.
 */
export class FieldResolver {
  constructor(private cfg: KanbanConfig) {}

  fieldId(name: string): string {
    const id = this.cfg.fields[name]
    if (!id) {
      const valid = Object.keys(this.cfg.fields).join(", ")
      throw new Error(`Unknown field: ${name}. Valid fields: ${valid}`)
    }
    return id
  }

  optionId(category: keyof KanbanConfig["options"], name: string): string {
    const options = this.cfg.options[category]
    if (!options) throw new Error(`Unknown option category: ${category}`)
    const id = options[name]
    if (!id) {
      const valid = Object.keys(options).join(", ")
      throw new Error(`Unknown option "${name}" in category "${category}". Valid options: ${valid}`)
    }
    return id
  }

  status(name: string) { return this.optionId("status", name) }
  version(name: string) { return this.optionId("version", name) }
  priority(name: string) { return this.optionId("priority", name) }
  decision(name: string) { return this.optionId("decision", name) }
  tipo(name: string) { return this.optionId("tipo", name) }
  area(name: string) { return this.optionId("area", name) }
  highlighted(name: string) { return this.optionId("highlighted", name) }

  /** Project node ID */
  get projectId() { return this.cfg.projectId }
  /** Repository node ID (for Draft→Issue conversion) */
  get repoId() { return this.cfg.repoId }
  /** Repository owner/name (e.g. jaminsmoke/Jarvis) */
  get repo() { return this.cfg.repo }
}
