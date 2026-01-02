/**
 * Configures scrollspy using IntersectionObserver.
 * Highlights nav links based on which content is in the detection band.
 * Only observes elements whose IDs have matching nav links.
 */
export const configureScrollspy = (container: Element | null, nav: Element | null) => {
  if (!(container && nav)) return () => {}

  const navLinks = nav.querySelectorAll("a.nav-link[href^='#']")
  const items = container.querySelectorAll("[id]")
  if (!(navLinks.length && items.length)) return () => {}

  // Build ID -> link map
  const idToLink = new Map<string, HTMLAnchorElement>()
  for (const link of navLinks) {
    idToLink.set(link.hash.slice(1), link)
  }

  let currentActive: string | null = null

  const setActive = (id: string | null) => {
    if (currentActive === id) return
    if (currentActive) idToLink.get(currentActive)!.classList.remove("active")
    if (id) idToLink.get(id)!.classList.add("active")
    currentActive = id
  }

  // Track which IDs are currently intersecting the detection band
  const intersecting = new Set<string>()

  const updateActive = () => {
    // Find first intersecting entry in DOM order that has a matching nav link
    const activeItem = Array.from(items).find(
      (item) => intersecting.has(item.id) && idToLink.has(item.id),
    )
    setActive(activeItem?.id ?? null)
  }

  // Detection band in top 40%
  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          intersecting.add(entry.target.id)
        } else {
          intersecting.delete(entry.target.id)
        }
      }
      updateActive()
    },
    {
      root: null,
      rootMargin: "-40% 0px -60% 0px",
      threshold: 0,
    },
  )

  for (const item of items) observer.observe(item)

  return () => observer.disconnect()
}
