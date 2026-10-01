import { routerCtx, routerRemoveQueryParam } from "@index/router"
import { isBreakpointUp, isLoggedIn } from "@utils/config"
import { useDisposeEffect } from "@utils/dispose-scope"
import { Collapse, Tooltip } from "bootstrap"
import { t } from "i18next"
import type { RefObject } from "preact"

export const useEditHelp = (anchorRef: RefObject<HTMLAnchorElement>) => {
  const active = isLoggedIn && routerCtx.value.queryParams.edit_help?.at(-1) === "1"

  useDisposeEffect(
    (scope) => {
      if (!active) return

      const anchor = anchorRef.current!
      const collapseRoot = anchor.closest(".navbar-collapse")!
      const collapse = Collapse.getOrCreateInstance(collapseRoot, { toggle: false })
      const tooltip = new Tooltip(anchor, {
        title: t("javascripts.edit_help"),
        placement: "bottom",
        trigger: "manual",
        animation: false,
      })
      let expanded = false
      let opening = false

      const show = () => {
        if (!isBreakpointUp("lg") && !collapseRoot.classList.contains("show")) {
          if (!collapseRoot.classList.contains("collapsing")) {
            expanded = true
            opening = true
            collapse.show()
          }
          return
        }
        tooltip.show()
      }
      const finish = () => routerRemoveQueryParam("edit_help")

      scope.dom(collapseRoot, "shown.bs.collapse", () => {
        opening = false
        show()
      })
      scope.dom(collapseRoot, "hide.bs.collapse", () => {
        opening = false
        tooltip.hide()
      })
      scope.dom(collapseRoot, "hidden.bs.collapse", show)
      scope.dom(window, "resize", show)
      scope.dom(document, "click", finish, { once: true })
      scope.dom(document, "keydown", (event) => {
        if (event.key === "Escape") finish()
      })
      show()

      return () => {
        tooltip.dispose()
        if (!expanded) return
        if (opening) {
          // Bootstrap ignores hide() during its opening transition.
          collapseRoot.addEventListener("shown.bs.collapse", () => collapse.hide(), {
            once: true,
          })
        } else {
          collapse.hide()
        }
      }
    },
    [active],
  )

  return active
}
