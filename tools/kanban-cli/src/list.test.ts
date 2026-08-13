import { describe, expect, test, beforeEach, mock } from "bun:test"
import { makeConfig } from "./fixtures"

interface TestItemNode {
  id: string
  content: { __typename: string; title: string; number?: number }
  fieldValues: { nodes: Array<{ name?: string; date?: string; field: { name: string } }> }
}

interface ItemsPageLike {
  node: { items: { nodes: TestItemNode[]; pageInfo: { hasNextPage: boolean; endCursor: string | null } } }
}

function makeNode(partial: {
  id?: string
  title?: string
  type?: "DraftIssue" | "Issue"
  number?: number
  fields?: Record<string, string>
}): TestItemNode {
  const fields = partial.fields ?? {}
  return {
    id: partial.id ?? "PVTI_x",
    content: {
      __typename: partial.type ?? "DraftIssue",
      title: partial.title ?? "Título",
      ...(partial.number !== undefined ? { number: partial.number } : {}),
    },
    fieldValues: {
      nodes: Object.entries(fields).map(([name, value]) => ({ name: value, field: { name } })),
    },
  }
}

function page(nodes: TestItemNode[], hasNextPage = false, endCursor: string | null = null): ItemsPageLike {
  return { node: { items: { nodes, pageInfo: { hasNextPage, endCursor } } } }
}

/** Página simple para fetchItems (sin filtros) o cola de páginas para fetchAllItems. */
let singlePage: ItemsPageLike | null = null
let allPagesQueue: ItemsPageLike[] = []

const gqlMock = mock(async (query: string, _vars: Record<string, unknown>) => {
  if (query.includes("items(first: 100")) {
    const p = allPagesQueue.shift()
    if (!p) throw new Error("mock: cola vacía para fetchAllItems")
    return p
  }
  if (query.includes("items(first: $limit")) {
    return singlePage
  }
  throw new Error(`mock: query no contemplada: ${query.slice(0, 60)}`)
})

mock.module("./client", () => ({ gql: gqlMock }))

// Import dinámico DESPUÉS de mock.module para que el mock esté registrado.
const { listItems } = await import("./list")

beforeEach(() => {
  singlePage = null
  allPagesQueue = []
  gqlMock.mockClear()
})

describe("listItems — sin filtros", () => {
  test("devuelve los items de una página con sus campos", async () => {
    singlePage = page([
      makeNode({ id: "A", title: "Item A", type: "Issue", number: 1, fields: { Status: "Detectado" } }),
      makeNode({ id: "B", title: "Item B", fields: { Status: "Debate" } }),
    ])
    const items = await listItems(makeConfig())
    expect(items).toHaveLength(2)
    expect(items[0]).toMatchObject({
      id: "A",
      title: "Item A",
      type: "Issue",
      number: 1,
      status: "Detectado",
    })
    expect(items[1]).toMatchObject({ id: "B", type: "DraftIssue", status: "Debate" })
  })

  test("usa el límite por defecto de 50", async () => {
    singlePage = page([])
    await listItems(makeConfig())
    const call = gqlMock.mock.calls.find((c) => String(c[0]).includes("items(first: $limit"))
    expect(call?.[1]).toMatchObject({ limit: 50 })
  })

  test("respeta el límite indicado", async () => {
    singlePage = page([])
    await listItems(makeConfig(), { limit: 10 })
    const call = gqlMock.mock.calls.find((c) => String(c[0]).includes("items(first: $limit"))
    expect(call?.[1]).toMatchObject({ limit: 10 })
  })
})

describe("listItems — filtros", () => {
  test("filtra por status", async () => {
    allPagesQueue = [
      page([
        makeNode({ id: "A", fields: { Status: "Detectado" } }),
        makeNode({ id: "B", fields: { Status: "Debate" } }),
        makeNode({ id: "C", fields: { Status: "Detectado" } }),
      ]),
    ]
    const items = await listItems(makeConfig(), { status: "Detectado" })
    expect(items.map((i) => i.id)).toEqual(["A", "C"])
  })

  test("filtra por múltiples criterios", async () => {
    allPagesQueue = [
      page([
        makeNode({ id: "A", fields: { Status: "Detectado", Tipo: "Bug", "Área principal": "kanban-cli" } }),
        makeNode({ id: "B", fields: { Status: "Detectado", Tipo: "Feature", "Área principal": "kanban-cli" } }),
      ]),
    ]
    const items = await listItems(makeConfig(), { status: "Detectado", tipo: "Bug", area: "kanban-cli" })
    expect(items.map((i) => i.id)).toEqual(["A"])
  })

  test("usa fetchAllItems (paginado) cuando hay filtros", async () => {
    allPagesQueue = [page([makeNode({ id: "A", fields: { Status: "Detectado" } })])]
    await listItems(makeConfig(), { status: "Detectado" })
    const allCall = gqlMock.mock.calls.find((c) => String(c[0]).includes("items(first: 100"))
    expect(allCall).toBeDefined()
  })
})

describe("listItems — paginación", () => {
  test("recorre todas las páginas hasta hasNextPage=false", async () => {
    allPagesQueue = [
      page([makeNode({ id: "A", fields: { Status: "Detectado" } })], true, "cursor1"),
      page([makeNode({ id: "B", fields: { Status: "Detectado" } })], false, null),
    ]
    const items = await listItems(makeConfig(), { status: "Detectado" })
    expect(items.map((i) => i.id)).toEqual(["A", "B"])
    const cursorCalls = gqlMock.mock.calls.filter((c) => String(c[0]).includes("items(first: 100"))
    expect(cursorCalls.map((c) => (c[1] as { cursor?: string | null }).cursor)).toEqual([null, "cursor1"])
  })

  test("corta si hasNextPage=true sin endCursor (seguridad anti-loop)", async () => {
    allPagesQueue = [page([makeNode({ id: "A", fields: { Status: "Detectado" } })], true, null)]
    const items = await listItems(makeConfig(), { status: "Detectado" })
    expect(items.map((i) => i.id)).toEqual(["A"])
  })
})

describe("listItems — valores por defecto y aliases", () => {
  test("campos ausentes → '-'", async () => {
    singlePage = page([makeNode({ id: "A" })])
    const items = await listItems(makeConfig())
    expect(items[0]).toMatchObject({ status: "-", version: "-", tipo: "-", area: "-" })
  })

  test("reconoce los aliases Version y Area", async () => {
    singlePage = page([makeNode({ id: "A", fields: { Version: "v0.1.0", Area: "Docs" } })])
    const items = await listItems(makeConfig())
    expect(items[0]).toMatchObject({ version: "v0.1.0", area: "Docs" })
  })
})
