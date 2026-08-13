import { describe, expect, test, beforeEach, mock } from "bun:test"
import { makeConfig } from "./fixtures"

const gqlMock = mock(async (query: string, vars: Record<string, unknown>) => {
  if (query.includes("createProjectV2View")) {
    return {
      createProjectV2View: {
        projectV2View: { id: "VIEW_1", number: 1, name: String(vars.name), layout: String(vars.layout) },
      },
    }
  }
  if (query.includes("updateProjectV2View")) {
    return {
      updateProjectV2View: {
        projectV2View: {
          id: String(vars.viewId),
          number: 1,
          name: vars.name ? String(vars.name) : "Vista",
          layout: vars.layout ? String(vars.layout) : "BOARD_LAYOUT",
        },
      },
    }
  }
  if (query.includes("deleteProjectV2View")) {
    return { deleteProjectV2View: { projectV2View: { id: vars.viewId } } }
  }
  throw new Error(`mock: query no contemplada: ${query.slice(0, 60)}`)
})

mock.module("./client", () => ({ gql: gqlMock }))
mock.module("./config", () => ({ loadConfig: () => makeConfig() }))

// Import dinámico DESPUÉS de mock.module para que los mocks estén registrados.
const { createView, updateView, deleteView } = await import("./views")

beforeEach(() => {
  gqlMock.mockClear()
})

describe("createView", () => {
  test("crea vista con layout por defecto BOARD_LAYOUT", async () => {
    const result = await createView("Mi vista")
    expect(result).toMatchObject({ id: "VIEW_1", name: "Mi vista", layout: "BOARD_LAYOUT" })

    const call = gqlMock.mock.calls.at(-1)
    expect(call?.[1]).toMatchObject({ projectId: "PVT_proj", name: "Mi vista", layout: "BOARD_LAYOUT" })
    expect((call?.[1] as Record<string, unknown>).configuration).toBeUndefined()
  })

  test("con visibleFieldIds incluye configuration en la mutación", async () => {
    await createView("Vista", "TABLE_LAYOUT", ["F1", "F2"])

    const call = gqlMock.mock.calls.at(-1)
    expect(call?.[1]).toMatchObject({
      layout: "TABLE_LAYOUT",
      configuration: { visibleFieldIds: ["F1", "F2"] },
    })
    const query = String(call?.[0])
    expect(query).toContain("$configuration: ProjectV2ViewConfigurationInput")
  })
})

describe("updateView", () => {
  test("envía null para lo que no se cambia", async () => {
    await updateView("VIEW_1", { name: "Renombrada" })

    const call = gqlMock.mock.calls.at(-1)
    expect(call?.[1]).toMatchObject({
      viewId: "VIEW_1",
      name: "Renombrada",
      layout: null,
      configuration: null,
    })
  })

  test("con visibleFieldIds arma configuration", async () => {
    await updateView("VIEW_1", { visibleFieldIds: ["F1"] })

    const call = gqlMock.mock.calls.at(-1)
    expect(call?.[1]).toMatchObject({ configuration: { visibleFieldIds: ["F1"] } })
  })

  test("devuelve la vista actualizada", async () => {
    const result = await updateView("VIEW_1", { name: "Nuevo nombre", layout: "ROADMAP_LAYOUT" })
    expect(result).toMatchObject({ id: "VIEW_1", name: "Nuevo nombre", layout: "ROADMAP_LAYOUT" })
  })
})

describe("deleteView", () => {
  test("devuelve el viewId borrado", async () => {
    const result = await deleteView("VIEW_9")
    expect(result).toEqual({ viewId: "VIEW_9" })
  })
})
