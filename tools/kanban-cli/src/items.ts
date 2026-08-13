import { gql } from "./client"
import { FieldResolver } from "./fields"
import { TEMPLATES, appendSection } from "./templates"
import { FIELD_TO_CATEGORY } from "./config"

interface CreateInput {
  title: string
  body?: string
  tipo?: string
  area?: string
  priority?: string
  version?: string
  extra?: Record<string, string>
}

interface CreateResult {
  itemId: string
  title: string
}

/**
 * Create a DraftIssue in the kanban with all fields set.
 */
export async function createItem(fields: FieldResolver, input: CreateInput): Promise<CreateResult> {
  const body = input.body ?? TEMPLATES.detectado(input.extra)
  const now = new Date()
  const inicioExacto = now.toISOString().replace(/\.\d{3}Z$/, "Z")
  const inicio = now.toISOString().slice(0, 10)

  // Resolve every field and option ID BEFORE creating the draft, so an invalid
  // name fails fast and never leaves an orphaned DraftIssue behind.
  // (These are resolved eagerly below via setFieldValue which uses FIELD_TO_CATEGORY)
  // addProjectV2DraftIssue returns the item ID directly (confirmed via API test).
  const createResult = await gql<{
    addProjectV2DraftIssue: { projectItem: { id: string } }
  }>(
    `mutation($projectId: ID!, $title: String!, $body: String!) {
      addProjectV2DraftIssue(input: { projectId: $projectId, title: $title, body: $body }) {
        projectItem { id }
      }
    }`,
    { projectId: fields.projectId, title: input.title, body }
  )

  const itemId = createResult.addProjectV2DraftIssue.projectItem.id

  // Set all fields via setFieldValue (DRY — same GraphQL mutations)
  await setFieldValue(fields, itemId, "Status", { option: "Detectado" })
  await setFieldValue(fields, itemId, "Versión", { option: input.version ?? "Sin asignar" })
  await setFieldValue(fields, itemId, "Prioridad", { option: input.priority ?? "Alta" })
  if (input.tipo) await setFieldValue(fields, itemId, "Tipo", { option: input.tipo })
  if (input.area) await setFieldValue(fields, itemId, "Área principal", { option: input.area })
  await setFieldValue(fields, itemId, "Inicio exacto", { text: inicioExacto })
  await setFieldValue(fields, itemId, "Inicio", { date: inicio })

  return { itemId, title: input.title }
}

interface SetFieldInput {
  option?: string
  text?: string
  date?: string
  force?: boolean
}

/** Valid status transitions. From → [allowed To] */
const VALID_TRANSITIONS: Record<string, string[]> = {
  Detectado: ["Debate"],
  Debate: ["Roadmap", "Detectado", "Changelog"],
  Roadmap: ["Ejecutando"],
  Ejecutando: ["Verificando"],
  Verificando: ["Changelog"],
}

/**
 * Validate that a status transition is allowed.
 * For Debate→Roadmap, also checks Decision=Aprobado.
 * For Debate→Detectado, checks Decision=Diferido.
 * For Debate→Changelog, checks Decision=Cancelado.
 */
async function validateTransition(
  itemId: string,
  fromStatus: string,
  toStatus: string,
  decision?: string,
): Promise<void> {
  const allowed = VALID_TRANSITIONS[fromStatus]
  if (!allowed || !allowed.includes(toStatus)) {
    const valid = allowed?.join(", ") ?? "ninguna"
    throw new Error(
      `Transición inválida: ${fromStatus} → ${toStatus}. Válidas desde ${fromStatus}: ${valid}. Usa --force para bypass.`
    )
  }

  // Special validation for Debate transitions
  if (fromStatus === "Debate") {
    if (toStatus === "Roadmap" && decision !== "Aprobado") {
      throw new Error(
        `Debate → Roadmap requiere Decision=Aprobado (actual: ${decision ?? "sin asignar"}). Usa --force para bypass.`
      )
    }
    if (toStatus === "Detectado" && decision !== "Diferido") {
      throw new Error(
        `Debate → Detectado requiere Decision=Diferido (actual: ${decision ?? "sin asignar"}). Usa --force para bypass.`
      )
    }
    if (toStatus === "Changelog" && decision !== "Cancelado") {
      throw new Error(
        `Debate → Changelog requiere Decision=Cancelado (actual: ${decision ?? "sin asignar"}). Usa --force para bypass.`
      )
    }
  }
}

/** Fetch current Status and Decision for an item. */
async function getItemStatus(itemId: string): Promise<{ status?: string; decision?: string }> {
  const result = await gql<{
    node: {
      fieldValues: {
        nodes: Array<{ name?: string; field: { name: string } }>
      }
    }
  }>(
    `query($itemId: ID!) {
      node(id: $itemId) {
        ... on ProjectV2Item {
          fieldValues(first: 20) {
            nodes {
              ... on ProjectV2ItemFieldSingleSelectValue { name, field { ... on ProjectV2FieldCommon { name } } }
            }
          }
        }
      }
    }`,
    { itemId },
  )

  const fv: Record<string, string> = {}
  for (const v of result.node.fieldValues.nodes) {
    if (v.name) fv[v.field.name] = v.name
  }
  // The field is "Decision" (config key); accept both spellings for robustness.
  return { status: fv["Status"], decision: fv["Decision"] ?? fv["Decisión"] }
}

/**
 * Set a field value on any item (Draft or Issue).
 * Supports single-select options, text and date values.
 * When setting Status, validates the transition unless force=true.
 */
export async function setFieldValue(
  fields: FieldResolver,
  itemId: string,
  fieldName: string,
  value: SetFieldInput,
): Promise<void> {
  const fieldId = fields.fieldId(fieldName)

  // Validate status transitions
  if (fieldName === "Status" && value.option) {
    const current = await getItemStatus(itemId)
    if (current.status && current.status !== value.option && !value.force) {
      await validateTransition(itemId, current.status, value.option, current.decision)
    }
  }

  if (value.option) {
    const category = FIELD_TO_CATEGORY[fieldName]
    if (!category) throw new Error(`No option category known for field: ${fieldName}`)
    const optionId = fields.optionId(category, value.option)
    await gql(
      `mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
        updateProjectV2ItemFieldValue(input: {
          projectId: $projectId, itemId: $itemId, fieldId: $fieldId,
          value: { singleSelectOptionId: $optionId }
        }) { clientMutationId }
      }`,
      { projectId: fields.projectId, itemId, fieldId, optionId }
    )
    return
  }

  if (value.text !== undefined) {
    await gql(
      `mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $text: String!) {
        updateProjectV2ItemFieldValue(input: {
          projectId: $projectId, itemId: $itemId, fieldId: $fieldId,
          value: { text: $text }
        }) { clientMutationId }
      }`,
      { projectId: fields.projectId, itemId, fieldId, text: value.text }
    )
    return
  }

  if (value.date) {
    await gql(
      `mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $date: Date!) {
        updateProjectV2ItemFieldValue(input: {
          projectId: $projectId, itemId: $itemId, fieldId: $fieldId,
          value: { date: $date }
        }) { clientMutationId }
      }`,
      { projectId: fields.projectId, itemId, fieldId, date: value.date }
    )
    return
  }

  throw new Error("Provide one of: --option, --text, --date")
}

/**
 * Get the current body of a DraftIssue.
 */
export async function getBody(itemId: string): Promise<string> {
  const result = await gql<{ node: { content: { body?: string; title?: string } } }>(
    `query($itemId: ID!) {
      node(id: $itemId) {
        ... on ProjectV2Item {
          content { ... on DraftIssue { body } ... on Issue { body } }
        }
      }
    }`,
    { itemId }
  )
  return result.node.content.body ?? ""
}

/**
 * Update the body of a DraftIssue. Keeps existing title.
 */
export async function updateBody(itemId: string, body: string): Promise<void> {
  // First get the draft Id (differs for Draft vs Issue)
  const item = await gql<{ node: { content: { __typename: string; id: string } } }>(
    `query($itemId: ID!) {
      node(id: $itemId) {
        ... on ProjectV2Item {
          content { __typename, ... on DraftIssue { id } ... on Issue { id } }
        }
      }
    }`,
    { itemId }
  )

  const content = item.node.content
  const __typename = content.__typename

  if (__typename === "DraftIssue") {
    await gql(
      `mutation($draftId: ID!, $body: String!) {
        updateProjectV2DraftIssue(input: { draftIssueId: $draftId, body: $body }) {
          clientMutationId
        }
      }`,
      { draftId: content.id, body }
    )
  } else {
    await gql(
      `mutation($issueId: ID!, $body: String!) {
        updateIssue(input: { id: $issueId, body: $body }) {
          clientMutationId
        }
      }`,
      { issueId: content.id, body }
    )
  }
}

/**
 * Append a section to an existing item body, then update it.
 */
export async function appendBodySection(itemId: string, sectionName: string, content: string): Promise<void> {
  const current = await getBody(itemId)
  const updated = appendSection(current, sectionName, content)
  await updateBody(itemId, updated)
}

/**
 * Move an item to a new position in the kanban.
 * Pass afterId to place after a specific item, or omit to move to top.
 */
export async function moveItem(
  projectId: string,
  itemId: string,
  afterId?: string,
): Promise<void> {
  await gql(
    `mutation($projectId: ID!, $itemId: ID!, $afterId: ID) {
      updateProjectV2ItemPosition(input: { projectId: $projectId, itemId: $itemId, afterId: $afterId }) {
        clientMutationId
      }
    }`,
    { projectId, itemId, afterId: afterId ?? null },
  )
}

/**
 * Archive an item in the project (soft delete).
 */
export async function archiveItem(projectId: string, itemId: string): Promise<void> {
  await gql(
    `mutation($projectId: ID!, $itemId: ID!) {
      archiveProjectV2Item(input: { projectId: $projectId, itemId: $itemId }) { clientMutationId }
    }`,
    { projectId, itemId },
  )
}

/**
 * Unarchive a previously archived item.
 */
export async function unarchiveItem(projectId: string, itemId: string): Promise<void> {
  await gql(
    `mutation($projectId: ID!, $itemId: ID!) {
      unarchiveProjectV2Item(input: { projectId: $projectId, itemId: $itemId }) { clientMutationId }
    }`,
    { projectId, itemId },
  )
}

/**
 * Permanently delete an item from the project (IRREVERSIBLE).
 * Unlike archive (soft delete), this removes the item entirely.
 * The caller is responsible for confirmation before calling this.
 */
export async function deleteItem(projectId: string, itemId: string): Promise<void> {
  await gql(
    `mutation($projectId: ID!, $itemId: ID!) {
      deleteProjectV2Item(input: { projectId: $projectId, itemId: $itemId }) { clientMutationId }
    }`,
    { projectId, itemId },
  )
}

/**
 * Permanently delete multiple items (batch). IRREVERSIBLE.
 * The caller is responsible for confirmation before calling this.
 */
export async function deleteItems(projectId: string, itemIds: string[]): Promise<void> {
  for (const itemId of itemIds) {
    await deleteItem(projectId, itemId)
  }
}

/**
 * Clear (remove) a field value from an item.
 */
export interface ShowItemResult {
  id: string
  title: string
  type: "DraftIssue" | "Issue"
  number?: number
  url?: string
  fields: Record<string, string>
  body: string
}

/**
 * Show all fields and metadata for a single item.
 * Fetches fieldValues via GraphQL and returns a structured result.
 */
export async function showItem(itemId: string): Promise<ShowItemResult> {
  const result = await gql<{
    node: {
      content: { __typename: string; title: string; number?: number; url?: string; body?: string }
      fieldValues: {
        nodes: Array<{
          name?: string
          date?: string
          text?: string
          field: { name: string }
        }>
      }
    }
  }>(
    `query($itemId: ID!) {
      node(id: $itemId) {
        ... on ProjectV2Item {
          content {
            __typename
            ... on DraftIssue { title, body }
            ... on Issue { title, number, url, body }
          }
          fieldValues(first: 30) {
            nodes {
              ... on ProjectV2ItemFieldSingleSelectValue { name, field { ... on ProjectV2FieldCommon { name } } }
              ... on ProjectV2ItemFieldDateValue { date, field { ... on ProjectV2FieldCommon { name } } }
              ... on ProjectV2ItemFieldTextValue { text, field { ... on ProjectV2FieldCommon { name } } }
            }
          }
        }
      }
    }`,
    { itemId },
  )

  const fields: Record<string, string> = {}
  for (const fv of result.node.fieldValues.nodes) {
    if (fv.name) fields[fv.field.name] = fv.name
    else if (fv.date) fields[fv.field.name] = fv.date
    else if (fv.text) fields[fv.field.name] = fv.text
  }

  const ct = result.node.content
  return {
    id: itemId,
    title: ct.title,
    type: ct.__typename as "DraftIssue" | "Issue",
    number: ct.number,
    url: ct.url,
    fields,
    body: ct.body ?? "",
  }
}

export async function clearFieldValue(
  projectId: string,
  itemId: string,
  fieldId: string,
): Promise<void> {
  await gql(
    `mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!) {
      clearProjectV2ItemFieldValue(input: { projectId: $projectId, itemId: $itemId, fieldId: $fieldId }) {
        clientMutationId
      }
    }`,
    { projectId, itemId, fieldId },
  )
}
