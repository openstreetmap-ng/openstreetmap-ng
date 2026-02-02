export const scrollElementIntoView = (
  container: Element | null | undefined,
  element: Element | null | undefined,
) => {
  if (!(container && element)) return

  const containerRect = container.getBoundingClientRect()
  const elementRect = element.getBoundingClientRect()

  const isVisible =
    elementRect.top >= containerRect.top && elementRect.bottom <= containerRect.bottom

  if (isVisible) return

  element.scrollIntoView({ block: "center" })
}
