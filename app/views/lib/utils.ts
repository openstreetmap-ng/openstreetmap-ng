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

const IPV4_MAPPED_IPV6_PREFIX = Uint8Array.of(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0xff, 0xff)

const startsWithBytes = (bytes: Uint8Array, prefix: Uint8Array) => {
  for (let i = 0; i < prefix.length; i++) {
    if (bytes[i] !== prefix[i]) return false
  }
  return true
}

const formatIpv4 = (bytes: Uint8Array, offset = 0) =>
  `${bytes[offset]}.${bytes[offset + 1]}.${bytes[offset + 2]}.${bytes[offset + 3]}`

export const formatPackedIp = (packedIp: Uint8Array) => {
  if (packedIp.length === 2) return `${packedIp[0]}.${packedIp[1]}.*.*`

  if (packedIp.length === 3) {
    if (packedIp[0] !== 0xff)
      throw new Error(`Unexpected packed IP length: ${packedIp.length}`)
    return `::ffff:${packedIp[1]}.${packedIp[2]}.*.*`
  }

  if (packedIp.length === 4) return formatIpv4(packedIp)

  if (packedIp.length === 6) {
    const groups = Array.from(
      { length: 3 },
      (_, i) => (packedIp[i * 2]! << 8) | packedIp[i * 2 + 1]!,
    )
    return `${groups[0]!.toString(16)}:${groups[1]!.toString(16)}:${groups[2]!.toString(16)}:*:*:*:*:*`
  }

  if (packedIp.length !== 16)
    throw new Error(`Unexpected packed IP length: ${packedIp.length}`)

  if (startsWithBytes(packedIp, IPV4_MAPPED_IPV6_PREFIX))
    return `::ffff:${formatIpv4(packedIp, 12)}`

  const groups = Array.from(
    { length: 8 },
    (_, i) => (packedIp[i * 2]! << 8) | packedIp[i * 2 + 1]!,
  )
  let bestStart = -1
  let bestLen = 0
  let currentStart = -1
  let currentLen = 0

  for (let i = 0; i <= groups.length; i++) {
    if (i < groups.length && groups[i] === 0) {
      if (currentStart === -1) currentStart = i
      currentLen += 1
      continue
    }
    if (currentLen >= 2 && currentLen > bestLen) {
      bestStart = currentStart
      bestLen = currentLen
    }
    currentStart = -1
    currentLen = 0
  }

  if (bestStart === -1) return groups.map((group) => group.toString(16)).join(":")

  const head = groups
    .slice(0, bestStart)
    .map((group) => group.toString(16))
    .join(":")
  const tail = groups
    .slice(bestStart + bestLen)
    .map((group) => group.toString(16))
    .join(":")
  if (!head && !tail) return "::"
  if (!head) return `::${tail}`
  if (!tail) return `${head}::`
  return `${head}::${tail}`
}
