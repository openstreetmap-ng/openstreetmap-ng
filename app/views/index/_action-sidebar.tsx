import { routerNavigateStrict } from "@index/router"
import { assertExists } from "@std/assert"
import { t } from "i18next"
import type { Map as MaplibreMap } from "maplibre-gl"
import type { ComponentChildren } from "preact"
import { collapseNavbar } from "../navbar/navbar"

const actionSidebars = document.querySelectorAll("div.action-sidebar")
const sidebarContainer = actionSidebars.length ? actionSidebars[0].parentElement : null

/** Get the action sidebar with the given class name */
export const getActionSidebar = (className: string) =>
  document.querySelector(`div.action-sidebar.${className}`)!

/** Switch the action sidebar with the given class name */
export const switchActionSidebar = (map: MaplibreMap, actionSidebar: HTMLElement) => {
  console.debug("ActionSidebar: Switching", actionSidebar.classList)
  assertExists(sidebarContainer)

  // Toggle all action sidebars
  for (const sidebar of actionSidebars) {
    const isTarget = sidebar === actionSidebar
    if (isTarget) {
      sidebarContainer.classList.toggle(
        "sidebar-overlay",
        sidebar.dataset.sidebarOverlay === "1",
      )
    }
    sidebar.classList.toggle("d-none", !isTarget)
  }

  map.resize()
  collapseNavbar()
}

/** On sidebar close button click, navigate to index */
const onCloseButtonClick = () => {
  console.debug("ActionSidebar: Close clicked")
  routerNavigateStrict("/")
}

/** Configure action sidebar events */
export const configureActionSidebar = (sidebar: Element) => {
  const closeButton = sidebar.querySelector(".sidebar-close-btn")
  closeButton?.addEventListener("click", onCloseButtonClick)
}

/** Sidebar header with close button */
export const SidebarHeader = ({
  title,
  class: className = "mb-3",
  children,
}: {
  title?: ComponentChildren
  class?: string
  children?: ComponentChildren
}) => (
  <div class={`row g-1 ${className}`}>
    <div class="col">{title ? <h2 class="sidebar-title">{title}</h2> : children}</div>
    <div class="col-auto">
      <button
        class="sidebar-close-btn btn-close"
        aria-label={t("javascripts.close")}
        type="button"
        onClick={onCloseButtonClick}
      />
    </div>
  </div>
)

/** Loading spinner */
export const LoadingSpinner = () => (
  <div class="text-center mt-4">
    <output class="spinner-border text-body-secondary">
      <span class="visually-hidden">{t("browse.start_rjs.loading")}</span>
    </output>
  </div>
)
