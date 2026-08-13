import { describe, expect, test } from "bun:test"
import { FieldResolver } from "./fields"
import { makeConfig } from "./fixtures"

describe("FieldResolver", () => {
  const fields = new FieldResolver(makeConfig())

  test("fieldId devuelve el ID de un campo conocido", () => {
    expect(fields.fieldId("Status")).toBe("F_status")
    expect(fields.fieldId("Área principal")).toBe("F_area")
  })

  test("fieldId lanza error para campo desconocido", () => {
    expect(() => fields.fieldId("Inexistente")).toThrow("Unknown field: Inexistente")
  })

  test("optionId devuelve el ID de una opción conocida", () => {
    expect(fields.optionId("status", "Detectado")).toBe("O_detectado")
    expect(fields.optionId("version", "v0.1.0")).toBe("O_v010")
  })

  test("optionId lanza error para opción desconocida", () => {
    expect(() => fields.optionId("status", "NoExiste")).toThrow(
      'Unknown option "NoExiste" in category "status"',
    )
  })

  test("helpers tipados resuelven por categoría", () => {
    expect(fields.status("Detectado")).toBe("O_detectado")
    expect(fields.version("v0.1.0")).toBe("O_v010")
    expect(fields.priority("Alta")).toBe("O_alta")
    expect(fields.decision("Aprobado")).toBe("O_aprobado")
    expect(fields.tipo("Bug")).toBe("O_bug")
    expect(fields.area("kanban-cli")).toBe("O_kc")
    expect(fields.highlighted("Yes")).toBe("O_yes")
  })

  test("getters de proyecto y repo", () => {
    expect(fields.projectId).toBe("PVT_proj")
    expect(fields.repoId).toBe("R_repo")
    expect(fields.repo).toBe("jaminsmoke/jarvis-skills")
  })
})
