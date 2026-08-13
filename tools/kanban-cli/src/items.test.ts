import { describe, expect, test, beforeEach, mock } from "bun:test"
import { makeConfig } from "./fixtures"

/** Estado simulado del item consultado por getItemStatus (fieldValues). */
const fakeState: { status?: string; decision?: string } = {}

/** Mock de gql que despacha según el contenido del query. */
const gqlMock = mock(async (query: string, _vars: Record<string, unknown>) => {
  if (query.includes("addProjectV2DraftIssue")) {
    return { addProjectV2DraftIssue: { projectItem: { id: "PVTI_item" } } }
  }
  if (query.includes("fieldValues(first: 20)")) {
    const nodes: Array<{ name: string; field: { name: string } }> = []
    if (fakeState.status) nodes.push({ name: fakeState.status, field: { name: "Status" } })
    if (fakeState.decision) nodes.push({ name: fakeState.decision, field: { name: "Decision" } })
    return { node: { fieldValues: { nodes } } }
  }
  if (query.includes("updateProjectV2ItemFieldValue")) {
    return {}
  }
  if (query.includes("deleteProjectV2Item")) {
    return { deleteProjectV2Item: { clientMutationId: "ok" } }
  }
  throw new Error(`mock: query no contemplada: ${query.slice(0, 60)}`)
})

mock.module("./client", () => ({ gql: gqlMock }))

// Import dinámico DESPUÉS de mock.module para que el mock esté registrado.
const { createItem, setFieldValue, deleteItem, deleteItems } = await import("./items")
const { FieldResolver } = await import("./fields")

const fields = new FieldResolver(makeConfig())

/** Llamadas de actualización de campo (query updateProjectV2ItemFieldValue). */
function updateCalls() {
  return gqlMock.mock.calls
    .filter((c) => String(c[0]).includes("updateProjectV2ItemFieldValue"))
    .map((c) => c[1] as Record<string, unknown>)
}

beforeEach(() => {
  fakeState.status = undefined
  fakeState.decision = undefined
  gqlMock.mockClear()
})

describe("createItem", () => {
  test("crea el draft y setea Status=Detectado + Versión/Prioridad por defecto", async () => {
    const result = await createItem(fields, { title: "Mi título" })

    expect(result.itemId).toBe("PVTI_item")
    expect(result.title).toBe("Mi título")

    const calls = updateCalls()
    const byField = (f: string) => calls.find((c) => c.fieldId === f)
    expect(byField("F_status")).toMatchObject({ optionId: "O_detectado" })
    expect(byField("F_version")).toMatchObject({ optionId: "O_sa" })
    expect(byField("F_priority")).toMatchObject({ optionId: "O_alta" })
  })

  test("setea tipo, área y fecha de inicio", async () => {
    await createItem(fields, { title: "T", tipo: "Bug", area: "kanban-cli" })

    const calls = updateCalls()
    const byField = (f: string) => calls.find((c) => c.fieldId === f)
    expect(byField("F_tipo")).toMatchObject({ optionId: "O_bug" })
    expect(byField("F_area")).toMatchObject({ optionId: "O_kc" })
    expect(byField("F_ie")).toHaveProperty("text")
    expect(byField("F_i")).toHaveProperty("date")
  })

  test("usa la plantilla detectado como body por defecto", async () => {
    await createItem(fields, { title: "T" })

    const createCall = gqlMock.mock.calls.find((c) => String(c[0]).includes("addProjectV2DraftIssue"))
    const body = (createCall?.[1] as { body?: string }).body ?? ""
    expect(body).toContain("## Contexto")
    expect(body).toContain("## Clasificación preliminar")
  })
})

describe("setFieldValue — validación de transiciones", () => {
  test("Detectado → Debate es válida y setea el option", async () => {
    fakeState.status = "Detectado"
    await setFieldValue(fields, "PVTI_item", "Status", { option: "Debate" })
    const last = updateCalls().at(-1)
    expect(last).toMatchObject({ optionId: "O_debate" })
  })

  test("Debate → Roadmap requiere Decision=Aprobado", async () => {
    fakeState.status = "Debate"
    fakeState.decision = "Pendiente"
    await expect(setFieldValue(fields, "PVTI_item", "Status", { option: "Roadmap" })).rejects.toThrow(
      "Debate → Roadmap requiere Decision=Aprobado",
    )
  })

  test("Debate → Roadmap con Decision=Aprobado es válida", async () => {
    fakeState.status = "Debate"
    fakeState.decision = "Aprobado"
    await setFieldValue(fields, "PVTI_item", "Status", { option: "Roadmap" })
    const last = updateCalls().at(-1)
    expect(last).toMatchObject({ optionId: "O_roadmap" })
  })

  test("Debate → Detectado requiere Decision=Diferido", async () => {
    fakeState.status = "Debate"
    fakeState.decision = "Aprobado"
    await expect(setFieldValue(fields, "PVTI_item", "Status", { option: "Detectado" })).rejects.toThrow(
      "Debate → Detectado requiere Decision=Diferido",
    )
  })

  test("Detectado → Roadmap es inválida (salto de estado)", async () => {
    fakeState.status = "Detectado"
    await expect(setFieldValue(fields, "PVTI_item", "Status", { option: "Roadmap" })).rejects.toThrow(
      "Transición inválida: Detectado → Roadmap",
    )
  })

  test("--force salta la validación", async () => {
    fakeState.status = "Detectado"
    await setFieldValue(fields, "PVTI_item", "Status", { option: "Roadmap", force: true })
    const last = updateCalls().at(-1)
    expect(last).toMatchObject({ optionId: "O_roadmap" })
  })

  test("mismo estado no valida (no-op safe)", async () => {
    fakeState.status = "Detectado"
    await setFieldValue(fields, "PVTI_item", "Status", { option: "Detectado" })
    const last = updateCalls().at(-1)
    expect(last).toMatchObject({ optionId: "O_detectado" })
  })
})

describe("deleteItem", () => {
  test("borra un item con la mutación deleteProjectV2Item", async () => {
    await deleteItem("PVT_proj", "PVTI_item")

    const call = gqlMock.mock.calls.find((c) => String(c[0]).includes("deleteProjectV2Item"))
    expect(call?.[1]).toMatchObject({ projectId: "PVT_proj", itemId: "PVTI_item" })
  })
})

describe("deleteItems (batch)", () => {
  test("borra cada item del lote en secuencia", async () => {
    await deleteItems("PVT_proj", ["PVTI_a", "PVTI_b", "PVTI_c"])

    const calls = gqlMock.mock.calls.filter((c) => String(c[0]).includes("deleteProjectV2Item"))
    expect(calls).toHaveLength(3)
    expect(calls.map((c) => c[1])).toEqual([
      { projectId: "PVT_proj", itemId: "PVTI_a" },
      { projectId: "PVT_proj", itemId: "PVTI_b" },
      { projectId: "PVT_proj", itemId: "PVTI_c" },
    ])
  })

  test("lote vacío no hace ninguna llamada", async () => {
    await deleteItems("PVT_proj", [])
    const calls = gqlMock.mock.calls.filter((c) => String(c[0]).includes("deleteProjectV2Item"))
    expect(calls).toHaveLength(0)
  })
})

describe("setFieldValue — text y date", () => {
  test("setea un campo de texto", async () => {
    await setFieldValue(fields, "PVTI_item", "Inicio exacto", { text: "2026-08-10T00:00:00Z" })
    const last = updateCalls().at(-1)
    expect(last).toMatchObject({ fieldId: "F_ie", text: "2026-08-10T00:00:00Z" })
  })

  test("setea un campo de fecha", async () => {
    await setFieldValue(fields, "PVTI_item", "Inicio", { date: "2026-08-10" })
    const last = updateCalls().at(-1)
    expect(last).toMatchObject({ fieldId: "F_i", date: "2026-08-10" })
  })
})
