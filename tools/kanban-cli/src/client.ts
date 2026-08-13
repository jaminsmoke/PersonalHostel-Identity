import { graphql } from "@octokit/graphql"
import { execSync } from "node:child_process"

function getGhToken(): string {
  try {
    return execSync("gh auth token", { encoding: "utf-8", stdio: ["pipe", "pipe", "pipe"] }).trim()
  } catch {
    throw new Error("gh CLI not authenticated. Run: gh auth login --scopes project,repo")
  }
}

export const gql = graphql.defaults({
  headers: {
    authorization: `token ${getGhToken()}`,
  },
})

/**
 * Run a typed GraphQL query against the GitHub API.
 * Wraps @octokit/graphql with the gh auth token.
 */
export async function query<T>(q: string, vars?: Record<string, unknown>): Promise<T> {
  return (await gql(q, vars ?? {})) as T
}
