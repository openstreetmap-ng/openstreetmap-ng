import { Map as MaplibreMap, type MapOptions } from "maplibre-gl"

export type MapInitErrorContext = Readonly<{
  container: HTMLElement
  heading: string
  details: string | undefined
  error: unknown
}>

const renderDefaultError = ({ container, heading, details }: MapInitErrorContext) => {
  const panel = document.createElement("div")
  panel.role = "alert"
  panel.style.paddingInline = "1rem"

  const title = document.createElement("h3")
  title.textContent = heading
  title.style.color = "#dc3545"
  panel.append(title)

  if (details) {
    const pre = document.createElement("pre")
    pre.textContent = details
    pre.style.color = "#58151c"
    pre.style.maxHeight = "15rem"
    pre.style.overflow = "auto"
    pre.style.overflowWrap = "anywhere"
    pre.style.whiteSpace = "pre-wrap"
    panel.append(pre)
  }

  container.replaceChildren(panel)
}

const formatError = ({ message, stack }: Error) => {
  let heading = message
  let details = stack

  const trimmedMessage = message.trim()
  if (trimmedMessage.startsWith("{") && trimmedMessage.endsWith("}")) {
    try {
      const parsed = JSON.parse(trimmedMessage) as { message?: unknown }
      if (typeof parsed.message === "string" && parsed.message.length > 0) {
        heading = parsed.message
        details = [JSON.stringify(parsed, null, 2), stack]
          .filter((part) => Boolean(part))
          .join("\n\n")
      }
    } catch {}
  }

  return {
    heading,
    details: details || undefined,
  }
}

export const configureMap = (
  options: Omit<MapOptions, "container"> & { container: HTMLElement },
  hooks?: { onInitError?: ((ctx: MapInitErrorContext) => void) | undefined },
) => {
  try {
    return new MaplibreMap(options)
  } catch (error) {
    const { heading, details } = formatError(error)
    const base = {
      container: options.container,
      heading,
      error,
    }
    const ctx = { ...base, details }
    if (hooks?.onInitError) hooks.onInitError(ctx)
    else renderDefaultError(ctx)

    queueMicrotask(() => {
      throw error
    })
    return null
  }
}
