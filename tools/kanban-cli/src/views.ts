import { gql } from "./client"
import { loadConfig } from "./config"

export type ViewLayout = "BOARD_LAYOUT" | "TABLE_LAYOUT" | "ROADMAP_LAYOUT"

export interface CreateViewResult {
  id: string
  number: number
  name: string
  layout: string
}

export interface UpdateViewResult {
  id: string
  number: number
  name: string
  layout: string
}

/**
 * Create a new view in the project.
 * Optionally pass visibleFieldIds to configure which fields are shown.
 */
export async function createView(
  name: string,
  layout: ViewLayout = "BOARD_LAYOUT",
  visibleFieldIds?: string[],
): Promise<CreateViewResult> {
  const cfg = loadConfig()

  const vars: Record<string, unknown> = {
    projectId: cfg.projectId,
    name,
    layout,
  }

  let mutation = `mutation($projectId: ID!, $name: String!, $layout: ProjectV2ViewLayout!) {
    createProjectV2View(input: { projectId: $projectId, name: $name, layout: $layout }) {
      projectV2View { id, number, name, layout }
    }
  }`

  if (visibleFieldIds?.length) {
    vars.configuration = { visibleFieldIds }
    mutation = `mutation($projectId: ID!, $name: String!, $layout: ProjectV2ViewLayout!, $configuration: ProjectV2ViewConfigurationInput) {
      createProjectV2View(input: { projectId: $projectId, name: $name, layout: $layout, configuration: $configuration }) {
        projectV2View { id, number, name, layout }
      }
    }`
  }

  const result = await gql<{
    createProjectV2View: { projectV2View: CreateViewResult }
  }>(mutation, vars)

  return result.createProjectV2View.projectV2View
}

/**
 * Update an existing view: rename, change layout, or update visible fields.
 * Pass only the options you want to change — null values are ignored by the API.
 */
export async function updateView(
  viewId: string,
  opts: { name?: string; layout?: ViewLayout; visibleFieldIds?: string[] },
): Promise<UpdateViewResult> {
  const vars: Record<string, unknown> = {
    viewId,
    name: opts.name ?? null,
    layout: opts.layout ?? null,
    configuration: opts.visibleFieldIds?.length ? { visibleFieldIds: opts.visibleFieldIds } : null,
  }

  const result = await gql<{
    updateProjectV2View: { projectV2View: UpdateViewResult }
  }>(
    `mutation($viewId: ID!, $name: String, $layout: ProjectV2ViewLayout, $configuration: ProjectV2ViewConfigurationInput) {
      updateProjectV2View(input: { viewId: $viewId, name: $name, layout: $layout, configuration: $configuration }) {
        projectV2View { id, number, name, layout }
      }
    }`,
    vars,
  )

  return result.updateProjectV2View.projectV2View
}

/**
 * Delete a view from the project. Cannot delete the last remaining view.
 */
export async function deleteView(viewId: string): Promise<{ viewId: string }> {
  const result = await gql<{ deleteProjectV2View: { projectV2View: { id: string } } }>(
    `mutation($viewId: ID!) {
      deleteProjectV2View(input: { viewId: $viewId }) { projectV2View { id } }
    }`,
    { viewId },
  )
  return { viewId: result.deleteProjectV2View.projectV2View.id }
}
