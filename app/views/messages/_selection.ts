/** Stop at the first failed item, leaving it and remaining items selected for retry. */
export const processSelection = async <T>(
  items: readonly T[],
  active: () => boolean,
  apply: (item: T) => Promise<void>,
  completed: (item: T) => void,
) => {
  for (const item of items) {
    if (!active()) return
    await apply(item)
    if (!active()) return
    completed(item)
  }
}
