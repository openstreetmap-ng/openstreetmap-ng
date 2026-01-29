import type { LonLatZoom } from "@lib/map/state"
import { isHrefCurrentPage, wrapMessageEventValidator } from "@lib/utils"
import { Collapse } from "bootstrap"
import { updateNavbarAndHash } from "./navbar-left"
import { messagesCountUnread } from "./navbar-right"

const navbar = document.querySelector(".navbar")
const navbarCollapseInstance = navbar
  ? new Collapse(navbar.querySelector(".navbar-collapse")!, { toggle: false })
  : null

/**
 * Collapse mobile navbar if currently expanded.
 * Improves user experience when navigating to a new page in SPA mode.
 */
export const collapseNavbar = () => {
  if (!navbarCollapseInstance) return
  navbarCollapseInstance.hide()
}

/** Update the unread messages badge in the navbar */
export const changeUnreadMessagesBadge = (change: number) => {
  const oldCount = messagesCountUnread.value
  const newCount = oldCount + change
  console.debug("Navbar: Message badge changed", oldCount, "->", newCount)
  messagesCountUnread.value = newCount
}

// Initialize active nav link
if (navbar) {
  for (const link of navbar.querySelectorAll("a.nav-link")) {
    if (isHrefCurrentPage(link.href)) {
      link.classList.add("active")
      link.ariaCurrent = "page"
      break
    }
  }
}

// Handle mapState window messages (from iD/Rapid)
window.addEventListener(
  "message",
  wrapMessageEventValidator(({ data }: MessageEvent) => {
    if (data.type !== "mapState") return
    const { lon, lat, zoom } = data.state as LonLatZoom
    updateNavbarAndHash({ lon, lat, zoom, layersCode: "" })
  }),
)
