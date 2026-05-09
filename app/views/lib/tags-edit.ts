export const formatTagsForTextEdit = (tags: Record<string, string>) =>
  Object.entries(tags)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, value]) => `${key}=${value}`)
    .join("\n")
