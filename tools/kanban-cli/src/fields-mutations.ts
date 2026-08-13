import { gql } from "./client"
import { loadConfig } from "./config"

/** Valid data types for custom fields */
export type FieldDataType = "TEXT" | "SINGLE_SELECT" | "MULTI_SELECT" | "NUMBER" | "DATE" | "ITERATION"

/** Valid colors for SingleSelect/MultiSelect options */
export type OptionColor = "GRAY" | "BLUE" | "GREEN" | "YELLOW" | "ORANGE" | "RED" | "PINK" | "PURPLE"

export interface FieldOption {
  name: string
  color: OptionColor
  description: string
}

export interface CreateFieldResult {
  fieldId: string
  name: string
  dataType: string
  options?: Array<{ id: string; name: string; color: string }>
}

export interface UpdateFieldResult {
  fieldId: string
  name: string
  options?: Array<{ id: string; name: string; color: string }>
}

/**
 * Create a new custom field in a GitHub Project V2.
 * Supports TEXT, SINGLE_SELECT, MULTI_SELECT, NUMBER, DATE, ITERATION.
 * For SINGLE_SELECT/MULTI_SELECT, pass initial options.
 */
export async function createField(
  name: string,
  dataType: FieldDataType,
  options?: FieldOption[],
): Promise<CreateFieldResult> {
  const cfg = loadConfig()

  const vars: Record<string, unknown> = {
    projectId: cfg.projectId,
    name,
    dataType,
  }

  let mutation = ""
  const isSelect = dataType === "SINGLE_SELECT" || dataType === "MULTI_SELECT"
  if (isSelect && options?.length) {
    const optKey = dataType === "SINGLE_SELECT" ? "singleSelectOptions" : "multiSelectOptions"
    const fragment = dataType === "SINGLE_SELECT" ? "ProjectV2SingleSelectField" : "ProjectV2MultiSelectField"
    mutation = `mutation($projectId: ID!, $name: String!, $dataType: ProjectV2CustomFieldType!, $options: [ProjectV2SingleSelectFieldOptionInput!]!) {
      createProjectV2Field(input: { projectId: $projectId, dataType: $dataType, name: $name, ${optKey}: $options }) {
        projectV2Field { ... on ${fragment} { id, name, dataType, options { id, name, color } } }
      }
    }`
    vars.options = options
  } else {
    mutation = `mutation($projectId: ID!, $name: String!, $dataType: ProjectV2CustomFieldType!) {
      createProjectV2Field(input: { projectId: $projectId, dataType: $dataType, name: $name }) {
        projectV2Field { ... on ProjectV2FieldCommon { id, name } }
      }
    }`
  }

  const result = await gql<{ createProjectV2Field: { projectV2Field: { id: string; name: string; dataType: string; options?: Array<{ id: string; name: string; color: string }> } } }>(mutation, vars)
  const f = result.createProjectV2Field.projectV2Field
  return { fieldId: f.id, name: f.name, dataType: f.dataType, options: f.options }
}

/**
 * Update an existing field. For SingleSelect/MultiSelect, pass the COMPLETE list
 * of options (existing + new) — this is a full replacement, not an append.
 * ⚠️ Option IDs will change. Re-query .kanbanrc.json after this.
 */
export async function updateField(
  fieldId: string,
  name?: string,
  singleSelectOptions?: FieldOption[],
): Promise<UpdateFieldResult> {
  const vars: Record<string, unknown> = { fieldId }
  if (name) vars.name = name
  if (singleSelectOptions) vars.singleSelectOptions = singleSelectOptions

  const mutation = `mutation($fieldId: ID!, $name: String, $singleSelectOptions: [ProjectV2SingleSelectFieldOptionInput!]) {
    updateProjectV2Field(input: { fieldId: $fieldId, name: $name, singleSelectOptions: $singleSelectOptions }) {
      projectV2Field { ... on ProjectV2SingleSelectField { id, name, options { id, name, color } } }
    }
  }`

  const result = await gql<{ updateProjectV2Field: { projectV2Field: { id: string; name: string; options?: Array<{ id: string; name: string; color: string }> } } }>(mutation, vars)
  const f = result.updateProjectV2Field.projectV2Field
  return { fieldId: f.id, name: f.name, options: f.options }
}

/**
 * Add a single option to an existing SingleSelect field.
 * Fetches current options (including descriptions), appends the new one, and calls updateField.
 * ⚠️ All option IDs will change after this operation.
 */
export async function addFieldOption(
  fieldId: string,
  newOption: FieldOption,
): Promise<UpdateFieldResult> {
  // Fetch current field options including descriptions
  const current = await gql<{
    node: { options: Array<{ id: string; name: string; color: string; description?: string }>; name: string }
  }>(
    `query($fieldId: ID!) {
      node(id: $fieldId) {
        ... on ProjectV2SingleSelectField { name, options { id, name, color, description } }
      }
    }`,
    { fieldId },
  )

  const existing: FieldOption[] = (current.node.options ?? []).map((o) => ({
    name: o.name,
    color: (o.color as OptionColor) ?? "GRAY",
    description: o.description ?? o.name,
  }))

  return updateField(fieldId, current.node.name, [...existing, newOption])
}

/**
 * Delete a custom field from a project.
 */
export async function deleteField(fieldId: string): Promise<void> {
  await gql(
    `mutation($fieldId: ID!) {
      deleteProjectV2Field(input: { fieldId: $fieldId }) { clientMutationId }
    }`,
    { fieldId },
  )
}
