let lastPrefix = ""

const originalTitle = document.title

export const setPageTitle = (prefix?: string | null | undefined) => {
  prefix ??= ""
  if (lastPrefix === prefix) return
  lastPrefix = prefix

  document.title = prefix ? `${prefix} | ${originalTitle}` : originalTitle
}
