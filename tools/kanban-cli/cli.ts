#!/usr/bin/env bun
/**
 * kanban-cli — GitHub Projects kanban toolkit
 *
 * Usage:
 *   bun cli.ts create --title "Fix X" --tipo Bug --area Desktop
 *   bun cli.ts body <itemId>              # read body
 *   bun cli.ts body <itemId> --set "..."  # replace body
 *   bun cli.ts body <itemId> --append "Sección" "..." # append section
 */

import { loadConfig } from "./src/config"
import { FieldResolver } from "./src/fields"

import { appendBodySection, createItem, getBody, updateBody, moveItem, archiveItem, unarchiveItem, deleteItems, clearFieldValue, setFieldValue, showItem } from "./src/items"
import { generateConfig, validateConfig } from "./src/config-tools"
import { listItems } from "./src/list"
import { createField, updateField, addFieldOption, deleteField } from "./src/fields-mutations"
import type { FieldDataType, OptionColor, FieldOption } from "./src/fields-mutations"
import { convertDraftToIssue } from "./src/conversions"
import { createView, updateView, deleteView } from "./src/views"
import { readFileSync, writeFileSync } from "node:fs"
import { resolve, dirname } from "node:path"
import { fileURLToPath } from "node:url"

const args = process.argv.slice(2)
const command = args[0]

function parseFlags(rest: string[]): Record<string, string> {
  const flags: Record<string, string> = {}
  for (let i = 0; i < rest.length; i++) {
    if (rest[i].startsWith("--")) {
      const key = rest[i].slice(2)
      const val = rest[i + 1] && !rest[i + 1].startsWith("--") ? rest[++i] : "true"
      flags[key] = val
    }
  }
  return flags
}

const VALID_COLORS = ["GRAY", "BLUE", "GREEN", "YELLOW", "ORANGE", "RED", "PINK", "PURPLE"]

function parseOptions(raw: string): Array<{ name: string; color: string; description: string }> {
  return raw.split(",").map((opt) => {
    const [name, color = "GRAY", description = ""] = opt.split(":")
    const c = color.trim().toUpperCase()
    if (!VALID_COLORS.includes(c)) {
      console.error(`Invalid color: ${c}. Valid: ${VALID_COLORS.join(", ")}`)
      process.exit(1)
    }
    return { name: name.trim(), color: c, description: description.trim() || name.trim() }
  })
}

async function main() {
  if (command === "--version") {
    const __filename = fileURLToPath(import.meta.url)
    const pkgPath = resolve(dirname(__filename), "package.json")
    const pkg = JSON.parse(readFileSync(pkgPath, "utf-8"))
    console.log(pkg.version)
    return
  }

  if (!command || command === "help" || command === "--help") {
    console.log(`kanban-cli — GitHub Projects kanban toolkit

Usage:
  bun cli.ts create --title "Fix X" --tipo Bug --area Desktop [--priority Alta] [--body "..."]
  bun cli.ts body <itemId>                   # read current body
  bun cli.ts body <itemId> --set "..."       # replace entire body
  bun cli.ts body <itemId> --append "Plan" --content "content"  # append a section
  bun cli.ts config generate --project PVT_...         # generate .kanbanrc.json
  bun cli.ts config validate                           # validate against Project
  bun cli.ts create-view --name "Mi Vista" [--layout BOARD_LAYOUT] [--visible-fields "Status,Versión,Tipo"]
  bun cli.ts update-view <viewId> [--name "..."] [--layout BOARD_LAYOUT] [--visible-fields "Status,..."]
  bun cli.ts delete-view <viewId>
  bun cli.ts show <itemId>                               # show all fields
  bun cli.ts list [--status X] [--tipo X] [--area X] [--format json]  # list items
  bun cli.ts create-field --name "..." --data-type SINGLE_SELECT [--options "A:GRAY,B:BLUE"]
  bun cli.ts update-field --field-id "..." [--name "..."] [--options "A:GRAY,B:BLUE"]
  bun cli.ts add-option --field-id "..." --name "..." --color GRAY --desc "..."
  bun cli.ts delete-field --field-id "..."
  bun cli.ts convert-draft <itemId>
  bun cli.ts move <itemId> [--after <afterItemId>]
  bun cli.ts set-field <itemId> --field "Status" --option "Roadmap" [--force]
  bun cli.ts set-field <itemId> --field "Inicio exacto" --text "2026-08-09T00:00:00Z"
  bun cli.ts set-field <itemId> --field "Completado" --date "2026-08-09"
  bun cli.ts archive <itemId>
  bun cli.ts unarchive <itemId>
  bun cli.ts delete <itemId> [más IDs...] [--yes]      # IRREVERSIBLE: requiere --yes
  bun cli.ts delete --status <estado> [--yes]          # borra todos los items de un status
  bun cli.ts clear-field <itemId> --field-id "..."
  bun cli.ts help                                      # show this help
`)
    return
  }

  // config generate does not require an existing .kanbanrc.json
  if (command === "config" && args[1] === "generate") {
    const flags = parseFlags(args.slice(2))
    const projectId = flags.project
    if (!projectId) {
      console.error("ERROR: --project <PROJECT_ID> is required")
      process.exit(1)
    }
    const generated = await generateConfig(projectId)
    writeFileSync(".kanbanrc.json", JSON.stringify(generated, null, 2) + "\n")
    console.log("Generated .kanbanrc.json with", Object.keys(generated.fields).length, "fields")
    console.log("⚠️  Fill in repoId and repo manually")
    return
  }

  const cfg = loadConfig()
  const fields = new FieldResolver(cfg)

  if (command === "create") {
    const flags = parseFlags(args.slice(1))
    if (!flags.title) {
      console.error("ERROR: --title is required")
      process.exit(1)
    }
    const result = await createItem(fields, {
      title: flags.title,
      body: flags.body,
      tipo: flags.tipo,
      area: flags.area,
      priority: flags.priority,
      version: flags.version,
    })
    console.log(JSON.stringify(result))
    return
  }

  if (command === "body") {
    const itemId = args[1]
    if (!itemId) {
      console.error("ERROR: itemId required")
      process.exit(1)
    }
    const flags = parseFlags(args.slice(2))

    if (flags.set) {
      await updateBody(itemId, flags.set)
      console.log("Body replaced OK")
    } else if (flags.append) {
      if (!flags.content) {
        console.error("ERROR: --append requires --content <text>")
        process.exit(1)
      }
      await appendBodySection(itemId, flags.append, flags.content)
      console.log(`Section "${flags.append}" appended OK`)
    } else {
      const body = await getBody(itemId)
      console.log(body)
    }
    return
  }

  if (command === "config") {
    const sub = args[1]
    const flags = parseFlags(args.slice(2))

    if (sub === "validate") {
      const issues = await validateConfig()
      if (issues.length === 0) {
        console.log("✅ .kanbanrc.json is valid")
      } else {
        console.log(`❌ ${issues.length} issues found:`)
        for (const i of issues) console.log("  -", i)
        process.exit(1)
      }
      return
    }

    console.error("Usage: bun cli.ts config <generate|validate>")
    process.exit(1)
  }

  if (command === "list") {
    const flags = parseFlags(args.slice(1))
    const items = await listItems(cfg, {
      status: flags.status,
      tipo: flags.tipo,
      area: flags.area,
      version: flags.version,
      limit: flags.limit ? parseInt(flags.limit) : 50,
    })
    if (flags.format === "json") {
      console.log(JSON.stringify(items, null, 2))
    } else {
      for (const item of items) {
        const num = item.number ? `#${item.number}` : "DRAFT"
        console.log(`${item.id} ${num.padEnd(6)} [${(item.status ?? "-").padEnd(12)}] ${(item.tipo ?? "-").padEnd(14)} ${(item.area ?? "-").padEnd(12)} ${item.title.slice(0, 80)}`)
      }
      console.log(`${items.length} items`)
    }
    return
  }

  if (command === "show") {
    const itemId = args[1]
    if (!itemId) { console.error("ERROR: itemId required"); process.exit(1) }
    const item = await showItem(itemId)
    const num = item.number ? `#${item.number}` : "DRAFT"
    console.log(`${num}  ${item.title}`)
    console.log(`Type: ${item.type}`)
    if (item.url) console.log(`URL: ${item.url}`)
    console.log("")
    for (const [name, value] of Object.entries(item.fields)) {
      console.log(`${name.padEnd(20)} ${value}`)
    }
    if (item.body) {
      console.log("")
      console.log("--- Body ---")
      console.log(item.body.slice(0, 500))
    }
    return
  }

  if (command === "create-view") {
    const flags = parseFlags(args.slice(1))
    if (!flags.name) {
      console.error("ERROR: --name is required")
      process.exit(1)
    }
    const layout = (flags.layout ?? "BOARD_LAYOUT").toUpperCase()
    if (!["BOARD_LAYOUT", "TABLE_LAYOUT", "ROADMAP_LAYOUT"].includes(layout)) {
      console.error(`ERROR: invalid layout "${layout}". Valid: BOARD_LAYOUT, TABLE_LAYOUT, ROADMAP_LAYOUT`)
      process.exit(1)
    }
    let visibleFieldIds: string[] | undefined
    if (flags["visible-fields"]) {
      visibleFieldIds = []
      for (const f of flags["visible-fields"].split(",")) {
        const name = f.trim()
        try { visibleFieldIds.push(fields.fieldId(name)) }
        catch { console.warn(`⚠️  Skipping unknown field: "${name}"`) }
      }
    }
    const result = await createView(flags.name, layout as "BOARD_LAYOUT" | "TABLE_LAYOUT" | "ROADMAP_LAYOUT", visibleFieldIds)
    console.log(JSON.stringify(result, null, 2))
    return
  }

  if (command === "update-view") {
    const viewId = args[1]
    if (!viewId) { console.error("ERROR: viewId required"); process.exit(1) }
    const flags = parseFlags(args.slice(2))
    const layout = flags.layout?.toUpperCase()
    if (layout && !["BOARD_LAYOUT", "TABLE_LAYOUT", "ROADMAP_LAYOUT"].includes(layout)) {
      console.error(`ERROR: invalid layout "${layout}". Valid: BOARD_LAYOUT, TABLE_LAYOUT, ROADMAP_LAYOUT`)
      process.exit(1)
    }
    let visibleFieldIds: string[] | undefined
    if (flags["visible-fields"]) {
      visibleFieldIds = []
      for (const f of flags["visible-fields"].split(",")) {
        const name = f.trim()
        try { visibleFieldIds.push(fields.fieldId(name)) }
        catch { console.warn(`⚠️  Skipping unknown field: "${name}"`) }
      }
    }
    const result = await updateView(viewId, {
      name: flags.name,
      layout: layout as "BOARD_LAYOUT" | "TABLE_LAYOUT" | "ROADMAP_LAYOUT" | undefined,
      visibleFieldIds,
    })
    console.log(JSON.stringify(result, null, 2))
    return
  }

  if (command === "delete-view") {
    const viewId = args[1]
    if (!viewId) { console.error("ERROR: viewId required"); process.exit(1) }
    const result = await deleteView(viewId)
    console.log(JSON.stringify(result, null, 2))
    return
  }

  if (command === "create-field") {
    const flags = parseFlags(args.slice(1))
    if (!flags.name || !flags["data-type"]) {
      console.error("ERROR: --name and --data-type are required")
      process.exit(1)
    }

    const dataType = flags["data-type"].toUpperCase() as FieldDataType
    let options: FieldOption[] | undefined

    if (flags.options) {
      options = parseOptions(flags.options) as FieldOption[]
    }

    const result = await createField(flags.name, dataType, options)
    console.log(JSON.stringify(result, null, 2))
    return
  }

  if (command === "update-field") {
    const flags = parseFlags(args.slice(1))
    if (!flags["field-id"]) {
      console.error("ERROR: --field-id is required")
      process.exit(1)
    }

    let options: FieldOption[] | undefined
    if (flags.options) {
      options = parseOptions(flags.options) as FieldOption[]
    }

    const result = await updateField(flags["field-id"], flags.name, options)
    console.log(JSON.stringify(result, null, 2))
    return
  }

  if (command === "add-option") {
    const flags = parseFlags(args.slice(1))
    if (!flags["field-id"] || !flags.name || !flags.color) {
      console.error("ERROR: --field-id, --name, and --color are required")
      process.exit(1)
    }

    const color = flags.color.toUpperCase()
    if (!VALID_COLORS.includes(color)) {
      console.error(`Invalid color: ${color}. Valid: ${VALID_COLORS.join(", ")}`)
      process.exit(1)
    }

    const option: FieldOption = {
      name: flags.name,
      color: color as OptionColor,
      description: flags.desc ?? flags.name,
    }

    const result = await addFieldOption(flags["field-id"], option)
    console.log(JSON.stringify(result, null, 2))
    console.log("⚠️  Option IDs changed. Run 'bun cli.ts config generate --project ...' to sync .kanbanrc.json")
    return
  }

  if (command === "delete-field") {
    const flags = parseFlags(args.slice(1))
    if (!flags["field-id"]) {
      console.error("ERROR: --field-id is required")
      process.exit(1)
    }

    await deleteField(flags["field-id"])
    console.log(`Field ${flags["field-id"]} deleted OK`)
    return
  }

  if (command === "convert-draft") {
    const itemId = args[1]
    if (!itemId) {
      console.error("ERROR: itemId required")
      process.exit(1)
    }

    const result = await convertDraftToIssue(itemId)
    console.log(JSON.stringify(result, null, 2))
    return
  }

  if (command === "move") {
    const itemId = args[1]
    if (!itemId) {
      console.error("ERROR: itemId required")
      process.exit(1)
    }
    const flags = parseFlags(args.slice(2))
    await moveItem(cfg.projectId, itemId, flags.after)
    console.log(`Item ${itemId} moved${flags.after ? ` after ${flags.after}` : " to top"}`)
    return
  }

  if (command === "set-field") {
    const itemId = args[1]
    if (!itemId) {
      console.error("ERROR: itemId required")
      process.exit(1)
    }
    const flags = parseFlags(args.slice(2))
    if (!flags.field) {
      console.error("ERROR: --field <fieldName> is required")
      process.exit(1)
    }
    await setFieldValue(fields, itemId, flags.field, {
      option: flags.option,
      text: flags.text,
      date: flags.date,
      force: flags.force === "true",
    })
    console.log(`Field "${flags.field}" set on ${itemId}`)
    return
  }

  if (command === "archive") {
    const itemId = args[1]
    if (!itemId) {
      console.error("ERROR: itemId required")
      process.exit(1)
    }
    await archiveItem(cfg.projectId, itemId)
    console.log(`Item ${itemId} archived`)
    return
  }

  if (command === "unarchive") {
    const itemId = args[1]
    if (!itemId) {
      console.error("ERROR: itemId required")
      process.exit(1)
    }
    await unarchiveItem(cfg.projectId, itemId)
    console.log(`Item ${itemId} unarchived`)
    return
  }

  if (command === "delete") {
    const flags = parseFlags(args.slice(1))
    const positional = args.slice(1).filter((a) => !a.startsWith("--"))

    let ids: string[]
    let titles: string[]
    let isIssue: boolean[]

    if (flags.status) {
      // Batch por status: resolver IDs y títulos vía listItems
      const items = await listItems(cfg, { status: flags.status })
      if (items.length === 0) {
        console.error(`ERROR: no hay items con status "${flags.status}"`)
        process.exit(1)
      }
      ids = items.map((i) => i.id)
      titles = items.map((i) => i.title)
      isIssue = items.map((i) => i.type === "Issue")
    } else {
      // Uno o varios IDs posicionales
      if (positional.length === 0) {
        console.error("ERROR: itemId(s) required o --status <estado>")
        process.exit(1)
      }
      ids = positional
      const shown = await Promise.all(ids.map((id) => showItem(id).catch(() => null)))
      titles = shown.map((s) => s?.title ?? "?")
      isIssue = shown.map((s) => s?.type === "Issue")
    }

    // IRREVERSIBLE: show what will be deleted, then require explicit --yes
    console.log(`⚠️  IRREVERSIBLE: se eliminarán ${ids.length} item(s):`)
    for (let i = 0; i < ids.length; i++) {
      const tag = isIssue[i] ? "[Issue]" : "[Draft]"
      console.log(`  - ${tag} ${titles[i]} (${ids[i]})`)
    }
    if (isIssue.some(Boolean)) {
      console.warn(
        "⚠️  OJO: algunos items son Issues reales. deleteProjectV2Item los desvincula del proyecto pero NO cierra/borra el Issue de GitHub."
      )
    }
    if (flags.yes !== "true") {
      console.error("ERROR: delete is IRREVERSIBLE. Confirm with --yes")
      process.exit(1)
    }
    await deleteItems(cfg.projectId, ids)
    console.log(`${ids.length} item(s) deleted permanently`)
    return
  }

  if (command === "clear-field") {
    const itemId = args[1]
    if (!itemId) {
      console.error("ERROR: itemId required")
      process.exit(1)
    }
    const flags = parseFlags(args.slice(2))
    if (!flags["field-id"]) {
      console.error("ERROR: --field-id is required")
      process.exit(1)
    }
    await clearFieldValue(cfg.projectId, itemId, flags["field-id"])
    console.log(`Field ${flags["field-id"]} cleared from item ${itemId}`)
    return
  }

  console.error(`Unknown command: ${command}. Run "bun cli.ts help" for usage.`)
  process.exit(1)
}

main().catch((e) => {
  console.error("ERROR:", e.message)
  process.exit(1)
})
