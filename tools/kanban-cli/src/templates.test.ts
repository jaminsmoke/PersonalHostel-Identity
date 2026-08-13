import { describe, expect, test } from "bun:test"
import { TEMPLATES, appendSection } from "./templates"

describe("TEMPLATES.detectado", () => {
  test("genera todas las secciones con placeholders por defecto", () => {
    const body = TEMPLATES.detectado()
    for (const section of [
      "## Contexto",
      "## Hallazgo y evidencia",
      "## Impacto",
      "## Alcance a debatir",
      "## Preguntas para Debate",
      "## Criterio para avanzar",
      "## Clasificación preliminar",
    ]) {
      expect(body).toContain(section)
    }
    expect(body).toContain("<situación, objetivo, por qué importa ahora>")
    expect(body).toContain("- Tipo: <bug|feature|maintenance|security|decision>")
    expect(body).toContain("- Prioridad: <Alta|Media|Baja>")
  })

  test("interpola los campos extra proporcionados", () => {
    const body = TEMPLATES.detectado({
      contexto: "CLI sin tests",
      hallazgo: "package.json sin script de test",
      tipo: "maintenance",
      area: "kanban-cli",
      prioridad: "Media",
      version: "v0.1.0",
    })
    expect(body).toContain("## Contexto\nCLI sin tests")
    expect(body).toContain("## Hallazgo y evidencia\npackage.json sin script de test")
    expect(body).toContain("- Tipo: maintenance")
    expect(body).toContain("- Área: kanban-cli")
    expect(body).toContain("- Prioridad: Media")
    expect(body).toContain("- Versión objetivo: v0.1.0")
  })
})

describe("appendSection", () => {
  test("añade una sección nueva al final si no existe", () => {
    const body = "## Contexto\ncontexto"
    const result = appendSection(body, "Impacto", "impacto")
    expect(result).toBe("## Contexto\ncontexto\n\n## Impacto\nimpacto")
  })

  test("reemplaza una sección existente", () => {
    const body = "## Contexto\ncontexto\n\n## Impacto\nviejo"
    const result = appendSection(body, "Impacto", "nuevo")
    expect(result).toBe("## Contexto\ncontexto\n\n## Impacto\nnuevo")
  })

  test("reemplaza solo la sección indicada y conserva las demás", () => {
    const body = "## Contexto\ncontexto\n\n## Impacto\nviejo\n\n## Criterio\ncriterio"
    const result = appendSection(body, "Impacto", "nuevo")
    expect(result).toBe("## Contexto\ncontexto\n\n## Impacto\nnuevo\n\n## Criterio\ncriterio")
  })

  test("body vacío añade la sección", () => {
    const result = appendSection("", "Plan", "plan")
    expect(result).toBe("\n\n## Plan\nplan")
  })
})
