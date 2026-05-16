import { SECOND } from "@std/datetime/constants"

export const isUnmodifiedLeftClick = (event: MouseEvent) =>
  !event.defaultPrevented &&
  event.button === 0 &&
  !event.metaKey &&
  !event.ctrlKey &&
  !event.shiftKey &&
  !event.altKey

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

export const throwAbortError = (message = "Operation cancelled by user"): never => {
  throw new DOMException(message, "AbortError")
}
