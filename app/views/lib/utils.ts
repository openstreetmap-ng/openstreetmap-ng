/** Check if the given href is the current page */
export const isHrefCurrentPage = (href: string): boolean => {
    const hrefPathname = new URL(href).pathname
    const locationPathname = window.location.pathname
    return hrefPathname === locationPathname || `${hrefPathname}/` === locationPathname
}

/**
 * Get the current unix timestamp
 * @example
 * getUnixTimestamp()
 * // => 1717761123
 */
export const getUnixTimestamp = (): number => (Date.now() / 1000) | 0

/**
 * Create a Python-like range of numbers
 * @example
 * range(1, 5)
 * // => [1, 2, 3, 4]
 */
export const range = (start: number, stop: number, step = 1): number[] => {
    const result: number[] = []
    for (let i = start; i < stop; i += step) result.push(i)
    return result
}

/**
 * Compute the modulo of a number, supporting negative numbers
 * @example
 * mod(-1, 3)
 * // => 2
 */
export const mod = (n: number, m: number): number => ((n % m) + m) % m

/** Decodes a URL-encoded string, converting both %xx sequences and + characters to their original form */
export const unquotePlus = (str: string): string =>
    decodeURIComponent(str.replaceAll("+", " "))

/** Matches any non-digit character */
export const NON_DIGIT_RE = /\D/g

const EVENT_ORIGIN_REGEX = /^https?:\/\/(?:www\.)?/
const CURRENT_HOST = `.${window.location.host.replace(/^www\./, "")}`

/**
 * Wrap message event handler to accept only messages from trusted sources
 * @param fn - Message event handler
 * @param isParent - If true, only messages from child domains are accepted, otherwise only from parent domains
 */
export const wrapMessageEventValidator = <T extends (event: MessageEvent) => any>(
    fn: T,
    isParent = true,
): T =>
    ((event: MessageEvent) => {
        const eventHost = `.${event.origin.replace(EVENT_ORIGIN_REGEX, "")}`
        if (
            isParent
                ? eventHost.endsWith(CURRENT_HOST)
                : CURRENT_HOST.endsWith(eventHost)
        )
            return fn(event)
    }) as T
