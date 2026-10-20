import { Tooltip } from "bootstrap"

/** Show the one-shot edit-help tooltip. The returned function hides and disposes it. */
export const showEditHelpTooltip = (element: Element, title: string) => {
  const tooltip = new Tooltip(element, {
    title,
    placement: "bottom",
    trigger: "manual",
    // Finish show/hide synchronously. Disposing during the default fade races
    // Bootstrap's transition callback, which throws and leaves aria-describedby
    // on the trigger. This also covers a dismiss that arrives while opening.
    animation: false,
  })
  let disposed = false

  const dispose = () => {
    if (disposed) return
    disposed = true
    tooltip.hide()
    tooltip.dispose()
  }

  tooltip.show()
  return dispose
}
