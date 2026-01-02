const originalTitle = document.title

export const setPageTitle = (prefix?: string) => {
  document.title = prefix ? `${prefix} | ${originalTitle}` : originalTitle
}
