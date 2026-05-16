import { SECOND } from "@std/datetime/constants"

export const isHrefCurrentPage = (
  href: string,
  { includeSubpaths = false }: { includeSubpaths?: boolean } = {},
) => {
  const hrefPathname = new URL(href, window.location.href).pathname
  const locationPathname = window.location.pathname
  return (
    hrefPathname === locationPathname ||
    `${hrefPathname}/` === locationPathname ||
    (includeSubpaths && locationPathname.startsWith(`${hrefPathname}/`))
  )
}

export const isUnmodifiedLeftClick = (event: MouseEvent) =>
  !event.defaultPrevented &&
  event.button === 0 &&
  !event.metaKey &&
  !event.ctrlKey &&
  !event.shiftKey &&
  !event.altKey

/** Decodes a URL-encoded string, converting both %xx sequences and + characters to their original form */
export const unquotePlus = (str: string) => decodeURIComponent(str.replaceAll("+", " "))

/** Create a Python-like range [start, stop) */
export const range = (start: number, stop?: number, step = 1) => {
  if (stop === undefined) {
    stop = start
    start = 0
  }
  const result: number[] = []
  for (let i = start; i < stop; i += step) result.push(i)
  return result
}

/** Matches any non-digit character */
export const NON_DIGIT_RE = /\D/g

const EVENT_ORIGIN_REGEX = /^https?:\/\/(?:www\.)?/
const CURRENT_HOST = `.${window.location.host.replace(/^www\./, "")}`

/**
 * Wrap message event handler to accept only messages from trusted sources
 * @param fn - Message event handler
 * @param isParent - If true, only messages from child domains are accepted, otherwise only from parent domains
 */
export const wrapMessageEventValidator = <T extends (e: MessageEvent) => any>(
  fn: T,
  isParent = true,
) =>
  ((e: MessageEvent) => {
    const eventHost = `.${e.origin.replace(EVENT_ORIGIN_REGEX, "")}`
    if (isParent ? eventHost.endsWith(CURRENT_HOST) : CURRENT_HOST.endsWith(eventHost))
      return fn(e)
  }) as T

export const wrapIdleCallbackStatic = <T extends (...args: never[]) => void>(
  fn: T,
  timeout = 5 * SECOND,
) => {
  let idleCallbackId: number | undefined
  return ((...args) => {
    if (idleCallbackId !== undefined) cancelIdleCallback(idleCallbackId)
    idleCallbackId = requestIdleCallback(() => fn(...args), { timeout })
  }) as T
}

export const headersDate = (headers: Headers | null) => {
  const ms = Date.parse(headers?.get("date") ?? "")
  return BigInt(Math.trunc((Number.isNaN(ms) ? Date.now() : ms) / SECOND))
}

const LATIN1_DECODER = new TextDecoder("latin1")

export const encodeAscii = (bytes: Uint8Array) => LATIN1_DECODER.decode(bytes)

export const throwAbortError = (message = "Operation cancelled by user"): never => {
  throw new DOMException(message, "AbortError")
}
