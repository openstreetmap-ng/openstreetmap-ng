import { qsParseAll } from "@utils/query-string"
import { Tooltip } from "bootstrap"
import { t } from "i18next"

export const isEditHelpRequested = (search: string) =>
  qsParseAll(search).edit_help?.at(-1) === "1"

export const configureEditHelp = (target: HTMLElement, onComplete: () => void) => {
  const tooltip = new Tooltip(target, {
    title: t("javascripts.edit_help"),
    placement: "bottom",
    boundary: document.body,
    fallbackPlacements: [],
    trigger: "manual",
    animation: false,
  })
  const collapse = target.closest(".navbar-collapse")
  let disposed = false
  let visible = false

  const complete = () => {
    dispose()
    onComplete()
  }

  const show = () => {
    if (disposed) return
    if (!target.getClientRects().length) {
      tooltip.hide()
      visible = false
      document.body.removeEventListener("click", complete)
      return
    }
    if (visible) return
    tooltip.show()
    visible = true
    document.body.addEventListener("click", complete, { once: true })
  }

  const dispose = () => {
    if (disposed) return
    disposed = true
    document.body.removeEventListener("click", complete)
    collapse?.removeEventListener("shown.bs.collapse", show)
    window.removeEventListener("resize", show)
    tooltip.dispose()
  }

  collapse?.addEventListener("shown.bs.collapse", show)
  window.addEventListener("resize", show)
  show()
  return dispose
}
