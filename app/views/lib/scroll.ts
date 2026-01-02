export const scrollElementIntoView = (container: Element, element: Element) => {
  const containerRect = container.getBoundingClientRect()
  const elementRect = element.getBoundingClientRect()

  const isVisible =
    elementRect.top >= containerRect.top && elementRect.bottom <= containerRect.bottom

  if (isVisible) return

  element.scrollIntoView({ behavior: "smooth", block: "center" })
}
