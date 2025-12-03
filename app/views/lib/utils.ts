/**
 * Check if number is a valid longitude
 * @example
 * isLongitude(180)
 * // => true
 */
export const isLongitude = (lon: number): boolean => lon >= -180 && lon <= 180

/**
 * Check if number is a valid latitude
 * @example
 * isLatitude(90)
 * // => true
 */
export const isLatitude = (lat: number): boolean => lat >= -90 && lat <= 90

/**
 * Check if number is a valid zoom level
 * @example
 * isZoom(17)
 * // => true
 */
export const isZoom = (zoom: number): boolean => zoom >= 0 && zoom <= 25

/**
 * Get a zoom level as a string with 2 decimal places
 * @example
 * beautifyZoom(4.4321)
 * // => "4.43"
 */
export const beautifyZoom = (zoom: number): string =>
    (((zoom * 100) | 0) / 100).toString()

/**
 * Compute the coordinate precision for a given zoom level
 * @example
 * zoomPrecision(17)
 * // => 5
 */
export const zoomPrecision = (zoom: number): number =>
    Math.max(0, Math.ceil(Math.log(zoom | 0) / Math.LN2))

/**
 * Compute the modulo of a number, supporting negative numbers
 * @example
 * mod(-1, 3)
 * // => 2
 */
export const mod = (n: number, m: number): number => ((n % m) + m) % m

/**
 * Throttle a function to only be called at most once per delay
 * @example
 * throttle(() => console.log("Hello"), 1000)
 */
export const throttle = <T extends any[]>(
    func: (...args: T) => void,
    delay: number,
): ((...args: T) => void) => {
    let lastCalled = 0
    let timeout: ReturnType<typeof setTimeout> | null = null

    return (...args) => {
        clearTimeout(timeout)
        const now = performance.now()
        const timeElapsed = now - lastCalled
        const timeLeft = delay - timeElapsed

        if (timeLeft <= 0) {
            lastCalled = now
            func(...args)
        } else {
            timeout = setTimeout(() => {
                lastCalled = performance.now()
                func(...args)
            }, timeLeft)
        }
    }
}

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

/** Backwards-compatible requestAnimationFrame function */
export const requestAnimationFramePolyfill: (callback: FrameRequestCallback) => number =
    window.requestAnimationFrame ||
    ((callback) => window.setTimeout(() => callback(performance.now()), 30))

/** Backwards-compatible requestIdleCallback function */
export const requestIdleCallbackPolyfill: (
    callback: IdleRequestCallback,
    options?: IdleRequestOptions,
) => number =
    window.requestIdleCallback ||
    ((callback) => window.setTimeout(() => callback(null), 0))

export const cancelIdleCallbackPolyfill: (handle: number) => void =
    window.cancelIdleCallback || ((handle) => window.clearTimeout(handle))

/** Get the device theme preference, *NOT* the currently active theme */
export const getDeviceThemePreference = (): "light" | "dark" =>
    window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"

/** Cache a function result, ignoring passed arguments */
export const staticCache = <T extends (...args: any[]) => any>(fn: T): T => {
    let called = false
    let result: ReturnType<T> | undefined
    return ((...args) => {
        if (called) return result
        result = fn(...args)
        called = true
        return result
    }) as T
}

/** Memoize a function result, depending on the arguments */
export const memoize = <T extends (...args: any[]) => any>(fn: T): T => {
    const cache = new Map<string, ReturnType<T>>()
    return ((...args: Parameters<T>): ReturnType<T> => {
        const key = JSON.stringify(args)
        let cached = cache.get(key)
        if (cached === undefined) {
            cached = fn(...args)
            cache.set(key, cached)
        }
        return cached
    }) as T
}

/** Wrap a low-priority function to execute during idle time */
export const wrapIdleCallbackStatic = <T extends (...args: any[]) => any>(
    fn: T,
    timeout = 5000,
): T => {
    let idleCallbackId: number | null = null
    return ((...args: any[]) => {
        cancelIdleCallbackPolyfill(idleCallbackId)
        idleCallbackId = requestIdleCallbackPolyfill(() => fn(...args), { timeout })
    }) as T
}

const eventOriginRegex = /^https?:\/\/(?:www\.)?/
const currentHost = `.${window.location.host.replace(/^www\./, "")}`

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
        const eventHost = `.${event.origin.replace(eventOriginRegex, "")}`
        if (
            isParent ? eventHost.endsWith(currentHost) : currentHost.endsWith(eventHost)
        )
            return fn(event)
    }) as T

/** Decodes a URL-encoded string, converting both %xx sequences and + characters to their original form */
export const unquotePlus = (str: string): string =>
    decodeURIComponent(str.replace(/\+/g, " "))

/** Darken a hex color by a specified amount */
export const darkenColor = memoize((hex: string, amount: number): string => {
    const hexCode = hex.replace("#", "")

    let r: string
    let g: string
    let b: string
    if (hexCode.length === 3) {
        r = hexCode[0].repeat(2)
        g = hexCode[1].repeat(2)
        b = hexCode[2].repeat(2)
    } else if (hexCode.length === 6) {
        r = hexCode.slice(0, 2)
        g = hexCode.slice(2, 4)
        b = hexCode.slice(4, 6)
    } else {
        console.error("Invalid hex color", hex)
        return hex
    }

    const darken = (value: string): string =>
        Math.round(Number.parseInt(value, 16) * (1 - amount))
            .toString(16)
            .padStart(2, "0")

    return `#${darken(r)}${darken(g)}${darken(b)}`
})

const getB2HLut = staticCache(() =>
    Array.from({ length: 256 }, (_, i) => i.toString(16).padStart(2, "0")),
)

/** Convert a byte array to a hex string */
export const toHex = (bytes: Uint8Array): string => {
    const lut = getB2HLut()
    let out = ""
    for (const byte of bytes) out += lut[byte]
    return out
}

const getH2BLut = staticCache(() => {
    const lut = new Uint8Array(128)
    for (let i = 0; i < 10; i++) lut[48 + i] = i
    for (let i = 0; i < 6; i++) lut[65 + i] = 10 + i
    for (let i = 0; i < 6; i++) lut[97 + i] = 10 + i
    return lut
})

/** Convert a hex string to a byte array */
export const fromHex = (hex: string): Uint8Array => {
    const lut = getH2BLut()
    const len = hex.length >> 1
    const out = new Uint8Array(len)
    for (let i = 0; i < len; i++) {
        const j = i << 1
        out[i] = (lut[hex.charCodeAt(j)] << 4) | lut[hex.charCodeAt(j + 1)]
    }
    return out
}
