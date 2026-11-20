export type BulkAction = "read" | "unread" | "delete"

// Process a stable snapshot sequentially; one failed request must not block the rest.
export const runMessageBatch = async (
  ids: readonly bigint[],
  apply: (id: bigint) => Promise<void>,
) => {
  const failures: unknown[] = []
  for (const id of ids) {
    try {
      await apply(id)
    } catch (error) {
      failures.push(error)
    }
  }
  return failures
}
