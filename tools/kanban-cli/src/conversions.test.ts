import { describe, expect, test, beforeEach, mock } from "bun:test"
import { makeConfig } from "./fixtures"

const gqlMock = mock(async (query: string, vars: Record<string, unknown>) => {
  if (query.includes("convertProjectV2DraftIssueItemToIssue")) {
    return { convertProjectV2DraftIssueItemToIssue: { item: { id: vars.itemId } } }
  }
  if (query.includes("node(id: $itemId)")) {
    return { node: { content: { number: 42, url: "https://github.com/jaminsmoke/jarvis-skills/issues/42" } } }
  }
  throw new Error(`mock: query no contemplada: ${query.slice(0, 60)}`)
})

mock.module("./client", () => ({ gql: gqlMock }))
mock.module("./config", () => ({ loadConfig: () => makeConfig() }))

// Import dinámico DESPUÉS de mock.module para que los mocks estén registrados.
const { convertDraftToIssue } = await import("./conversions")

beforeEach(() => {
  gqlMock.mockClear()
})

describe("convertDraftToIssue", () => {
  test("convierte el draft y devuelve número y URL del issue", async () => {
    const result = await convertDraftToIssue("PVTI_item")

    expect(result.itemId).toBe("PVTI_item")
    expect(result.issueNumber).toBe(42)
    expect(result.issueUrl).toBe("https://github.com/jaminsmoke/jarvis-skills/issues/42")

    // La conversión usa el repoId del config cargado por defecto.
    const convertCall = gqlMock.mock.calls.find((c) => String(c[0]).includes("convertProjectV2DraftIssueItemToIssue"))
    expect(convertCall?.[1]).toMatchObject({ itemId: "PVTI_item", repoId: "R_repo" })
  })

  test("usa repositoryId explícito si se pasa", async () => {
    await convertDraftToIssue("PVTI_item", "R_override")

    const convertCall = gqlMock.mock.calls.find((c) => String(c[0]).includes("convertProjectV2DraftIssueItemToIssue"))
    expect(convertCall?.[1]).toMatchObject({ repoId: "R_override" })
  })
})
