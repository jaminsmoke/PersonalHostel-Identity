import { gql } from "./client"
import { loadConfig } from "./config"

export interface ConvertResult {
  itemId: string
  issueNumber: number
  issueUrl: string
}

/**
 * Convert a DraftIssue project item to a real Issue.
 * The project must be linked to the repository.
 * Returns the issue number and URL.
 */
export async function convertDraftToIssue(
  itemId: string,
  repositoryId?: string,
): Promise<ConvertResult> {
  const cfg = loadConfig()
  const repoId = repositoryId ?? cfg.repoId

  // Step 1: Convert
  await gql(
    `mutation($itemId: ID!, $repoId: ID!) {
      convertProjectV2DraftIssueItemToIssue(input: { itemId: $itemId, repositoryId: $repoId }) {
        item { id }
      }
    }`,
    { itemId, repoId },
  )

  // Step 2: Get the issue number
  const result = await gql<{
    node: { content: { number: number; url: string } }
  }>(
    `query($itemId: ID!) {
      node(id: $itemId) {
        ... on ProjectV2Item {
          content { ... on Issue { number, url } }
        }
      }
    }`,
    { itemId },
  )

  return {
    itemId,
    issueNumber: result.node.content.number,
    issueUrl: result.node.content.url,
  }
}
