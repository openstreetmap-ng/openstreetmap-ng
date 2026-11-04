import { Tooltip } from "bootstrap"

/** Show the one-click edit tutorial without changing map navigation state. */
export const showEditHelp = (
  anchor: HTMLElement,
  title: string,
  onFinish: () => void,
) => {
  const tooltip = new Tooltip(anchor, { title, placement: "bottom", trigger: "manual" })
  const events = new AbortController()
  let disposed = false
  const dispose = () => {
    if (disposed) return
    disposed = true
    events.abort()
    tooltip.dispose()
  }
  const finish = () => {
    const url = new URL(window.location.href)
    url.searchParams.delete("edit_help")
    window.history.replaceState(window.history.state, "", url)
    dispose()
    onFinish()
  }
  document.addEventListener("click", finish, { once: true, signal: events.signal })
  document.addEventListener(
    "keydown",
    (event) => {
      if (event.key === "Escape") finish()
    },
    { signal: events.signal },
  )
  tooltip.show()
  return dispose
}
