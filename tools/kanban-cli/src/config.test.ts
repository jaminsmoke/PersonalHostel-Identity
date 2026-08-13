import { describe, expect, test, beforeEach, afterEach } from "bun:test"
import { mkdtempSync, writeFileSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { loadConfig, _resetConfigForTests } from "./config"
import { makeConfig } from "./fixtures"

let dirs: string[] = []

function makeDir(files: Record<string, string>): string {
  const dir = mkdtempSync(join(tmpdir(), "kanban-test-"))
  for (const [name, content] of Object.entries(files)) {
    writeFileSync(join(dir, name), content)
  }
  dirs.push(dir)
  return dir
}

afterEach(() => {
  for (const d of dirs) rmSync(d, { recursive: true, force: true })
  dirs = []
})

// Reinicia la caché de módulo entre tests para que cada uno lea de disco.
beforeEach(() => {
  _resetConfigForTests()
})

const VALID_CONFIG = makeConfig()

function withCwd(dir: string, fn: () => void): void {
  const prev = process.cwd()
  process.chdir(dir)
  try {
    fn()
  } finally {
    process.chdir(prev)
  }
}

// La caché de módulo se reinicia en beforeEach, así que los tests son
// independientes del orden de ejecución.
describe("loadConfig", () => {
  test("lanza error si no existe .kanbanrc.json", () => {
    const dir = makeDir({})
    withCwd(dir, () => {
      expect(() => loadConfig()).toThrow(".kanbanrc.json not found")
    })
  })

  test("lanza error si el JSON es inválido", () => {
    const dir = makeDir({ ".kanbanrc.json": "{ not valid json" })
    withCwd(dir, () => {
      expect(() => loadConfig()).toThrow("Invalid JSON")
    })
  })

  test("lanza error si falta una key requerida", () => {
    const { options, ...sinOptions } = VALID_CONFIG
    const dir = makeDir({ ".kanbanrc.json": JSON.stringify(sinOptions) })
    withCwd(dir, () => {
      expect(() => loadConfig()).toThrow("missing required key: options")
    })
  })

  test("lanza error si falta un campo requerido", () => {
    const fieldsSinStatus = Object.fromEntries(
      Object.entries(VALID_CONFIG.fields).filter(([name]) => name !== "Status"),
    )
    const cfg = { ...VALID_CONFIG, fields: fieldsSinStatus }
    const dir = makeDir({ ".kanbanrc.json": JSON.stringify(cfg) })
    withCwd(dir, () => {
      expect(() => loadConfig()).toThrow("fields missing: Status")
    })
  })

  test("carga un config válido", () => {
    const dir = makeDir({ ".kanbanrc.json": JSON.stringify(VALID_CONFIG) })
    withCwd(dir, () => {
      const cfg = loadConfig()
      expect(cfg.projectId).toBe("PVT_proj")
      expect(cfg.fields.Status).toBe("F_status")
    })
  })
})
