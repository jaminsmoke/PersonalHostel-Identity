import { gql } from "./client"
import { loadConfig, FIELD_TO_CATEGORY, type KanbanConfig } from "./config"
import { writeFileSync } from "node:fs"

/**
 * Generate .kanbanrc.json from a GitHub Project V2.
 * Queries all fields and options and builds the config.
 */
export async function generateConfig(projectId: string): Promise<KanbanConfig> {
  const data = await gql<{
    node: {
      fields: {
        nodes: Array<{
          id: string
          name: string
          dataType: string
          options?: Array<{ id: string; name: string }>
        }>
      }
    }
  }>(
    `query($projectId: ID!) {
      node(id: $projectId) {
        ... on ProjectV2 {
          fields(first: 50) {
            nodes {
              ... on ProjectV2Field { id, name, dataType }
              ... on ProjectV2SingleSelectField { id, name, dataType, options { id, name } }
            }
          }
        }
      }
    }`,
    { projectId }
  )

  const fields: Record<string, string> = {}
  const options: KanbanConfig["options"] = {
    status: {},
    version: {},
    priority: {},
    decision: {},
    tipo: {},
    area: {},
    highlighted: {},
  }

  for (const f of data.node.fields.nodes) {
    if (f.name === "Title" || f.name === "Assignees" || f.name === "Labels" ||
        f.name === "Linked pull requests" || f.name === "Milestone" ||
        f.name === "Repository" || f.name === "Reviewers" ||
        f.name === "Parent issue" || f.name === "Sub-issues progress" ||
        f.name === "Created at" || f.dataType === "TITLE" || f.dataType === "ASSIGNEES" ||
        f.dataType === "LABELS" || f.dataType === "LINKED_PULL_REQUESTS" ||
        f.dataType === "MILESTONE" || f.dataType === "REPOSITORY" ||
        f.dataType === "REVIEWERS" || f.dataType === "PARENT_ISSUE" ||
        f.dataType === "SUB_ISSUES_PROGRESS") {
      continue
    }

    fields[f.name] = f.id

    const cat = FIELD_TO_CATEGORY[f.name]
    if (cat && f.options) {
      for (const o of f.options) {
        options[cat][o.name] = o.id
      }
    }
  }

  // Also query repo info
  const repoData = await gql<{ node: { title: string } }>(
    `query($projectId: ID!) { node(id: $projectId) { ... on ProjectV2 { title } } }`,
    { projectId }
  )

  return {
    projectId,
    repoId: "REPLACE_ME", // User must fill this in
    repo: "REPLACE_ME",   // User must fill this in
    fields,
    options,
  }
}

/**
 * Validate that .kanbanrc.json matches the real Project fields.
 * Returns array of issues found (empty = valid).
 */
export async function validateConfig(): Promise<string[]> {
  const cfg = loadConfig()
  const issues: string[] = []

  const data = await gql<{
    node: {
      fields: {
        nodes: Array<{
          id: string
          name: string
          options?: Array<{ id: string; name: string }>
        }>
      }
    }
  }>(
    `query($projectId: ID!) {
      node(id: $projectId) {
        ... on ProjectV2 {
          fields(first: 50) {
            nodes {
              ... on ProjectV2Field { id, name }
              ... on ProjectV2SingleSelectField { id, name, options { id, name } }
            }
          }
        }
      }
    }`,
    { projectId: cfg.projectId }
  )

  const realFields = new Map(data.node.fields.nodes.map(f => [f.name, f]))

  for (const [name, id] of Object.entries(cfg.fields)) {
    const real = realFields.get(name)
    if (!real) {
      issues.push(`Field "${name}" (${id}) not found in Project`)
    } else if (real.id !== id) {
      issues.push(`Field "${name}": config has ${id}, Project has ${real.id}`)
    }
  }

  for (const [cat, opts] of Object.entries(cfg.options)) {
    // Find the field name for this category via FIELD_TO_CATEGORY reverse lookup
    const fieldName = Object.entries(FIELD_TO_CATEGORY).find(([, c]) => c === cat)?.[0] ?? cat

    const real = realFields.get(fieldName)
    if (!real || !real.options) continue
    const realOptions = new Map(real.options.map(o => [o.name, o.id]))
    for (const [name, id] of Object.entries(opts)) {
      const realId = realOptions.get(name)
      if (!realId) {
        issues.push(`Option "${name}" in ${cat}: not found in Project`)
      } else if (realId !== id) {
        issues.push(`Option "${name}" in ${cat}: config has ${id}, Project has ${realId}`)
      }
    }
  }

  // Check for Drafts in wrong states (need to query items)
  const statusFieldId = cfg.fields["Status"]
  const executingId = cfg.options.status["Ejecutando"]
  const verifyingId = cfg.options.status["Verificando"]
  const changelogId = cfg.options.status["Changelog"]
  const forbiddenIds = [executingId, verifyingId, changelogId].filter(Boolean)

  if (statusFieldId && forbiddenIds.length > 0) {
    const itemsData = await gql<{
      node: {
        items: {
          nodes: Array<{
            id: string
            content: { __typename: string; title?: string; number?: number }
            fieldValues?: { nodes?: Array<{ field?: { id?: string }; name?: string; optionId?: string }> }
          }>
        }
      }
    }>(
      `query($projectId: ID!) {
        node(id: $projectId) {
          ... on ProjectV2 {
            items(first: 100) {
              nodes {
                id
                content { ... on DraftIssue { title } ... on Issue { title, number } }
                fieldValues(first: 20) {
                  nodes { ... on ProjectV2ItemFieldSingleSelectValue { field { ... on ProjectV2Field { id } }, name, optionId } }
                }
              }
            }
          }
        }
      }`,
      { projectId: cfg.projectId }
    )

    for (const item of itemsData.node.items.nodes) {
      const isDraft = !("number" in item.content)
      if (!isDraft) continue

      const statusVal = item.fieldValues?.nodes?.find(
        (fv: { field?: { id?: string } }) => fv.field?.id === statusFieldId
      )
      if (!statusVal) continue

      const optionId = (statusVal as { optionId?: string }).optionId
      if (optionId && forbiddenIds.includes(optionId)) {
        const title = item.content.title ?? "(sin titulo)"
        const statusName = statusVal.name ?? optionId
        issues.push(
          `DRAFT in forbidden state: "${title.slice(0, 50)}" is DraftIssue but Status=${statusName}. Convert to Issue first.`
        )
      }
    }
  }

  return issues
}
