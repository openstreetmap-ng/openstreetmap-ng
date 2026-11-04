/** Show the requested editing hint once, without changing unrelated URL state. */
export const configureEditHelp = (
  isLoggedIn: boolean,
  createTooltip: () => { show(): void; dispose(): void },
  page: Window = window,
) => {
  const url = new URL(page.location.href)
  if (!isLoggedIn || url.searchParams.get("edit_help") !== "1") return

  const tooltip = createTooltip()
  let disposed = false

  const cleanup = () => {
    if (disposed) return
    disposed = true
    page.document.body.removeEventListener("click", finish)
    page.document.removeEventListener("keydown", onKeyDown)
    tooltip.dispose()
  }

  const finish = () => {
    cleanup()
    // Map navigation may have updated the hash since the hint was shown.
    const current = new URL(page.location.href)
    current.searchParams.delete("edit_help")
    page.history.replaceState(page.history.state, "", current)
  }

  const onKeyDown = (event: KeyboardEvent) => {
    if (event.key === "Escape") finish()
  }

  tooltip.show()
  page.document.body.addEventListener("click", finish, { once: true })
  page.document.addEventListener("keydown", onKeyDown)
  return cleanup
}
