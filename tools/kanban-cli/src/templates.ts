/**
 * Body templates for each kanban stage.
 * Each template returns a string with the required sections.
 */

export const TEMPLATES = {
  detectado: (extra?: Record<string, string>) => `## Contexto
${extra?.contexto ?? "<situación, objetivo, por qué importa ahora>"}

## Hallazgo y evidencia
${extra?.hallazgo ?? "<hechos verificables, rutas, versiones, métricas>"}

## Impacto
${extra?.impacto ?? "<consecuencias técnicas, producto, seguridad>"}

## Alcance a debatir
${extra?.alcance ?? "<qué decidir, límites>"}

## Preguntas para Debate
${extra?.preguntas ?? "1. <pregunta>"}

## Criterio para avanzar
${extra?.criterio ?? "<evidencia mínima para pasar a Roadmap>"}

## Clasificación preliminar
- Tipo: ${extra?.tipo ?? "<bug|feature|maintenance|security|decision>"}
- Área: ${extra?.area ?? "<app|desktop|core|server|CI|infra|docs|lint|dependencies|release|governance|upstream>"}
- Labels esperadas: ${extra?.labels ?? "<label1>, <label2>"}
- Prioridad: ${extra?.prioridad ?? "<Alta|Media|Baja>"}
- Versión objetivo: ${extra?.version ?? "<siguiente a latest>"}`,

  decision: (decision: string) => `## Decisión acordada
${decision}
`,

  plan: (plan: string) => `## Plan aprobado
${plan}
`,

  implementacion: (impl: string) => `## Implementación
${impl}
`,
}

/** Append a section to an existing body. */
export function appendSection(body: string, sectionName: string, content: string): string {
  const marker = `## ${sectionName}`
  if (body.includes(marker)) {
    // Replace existing section
    const idx = body.indexOf(marker)
    const next = body.indexOf("\n## ", idx + marker.length)
    const before = body.slice(0, idx)
    const after = next === -1 ? "" : body.slice(next)
    return before + marker + "\n" + content + (after ? "\n" + after : "")
  }
  return body + "\n\n" + marker + "\n" + content
}
