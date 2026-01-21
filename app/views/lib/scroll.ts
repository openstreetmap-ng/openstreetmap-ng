export const scrollElementIntoView = (
  container: Element,
  element: Element | null | undefined,
) => {
  if (!element) return

  const containerRect = container.getBoundingClientRect()
  const elementRect = element.getBoundingClientRect()

  const isVisible =
    elementRect.top >= containerRect.top && elementRect.bottom <= containerRect.bottom

  if (isVisible) return

  element.scrollIntoView({ block: "center" })
}
