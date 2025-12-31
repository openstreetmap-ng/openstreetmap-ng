/**
 * Parse a query string into an object
 * @example
 * qsParse("?foo=bar&baz=qux")
 * // => { foo: "bar", baz: "qux" }
 */
export const qsParse = (qs: string) => {
    const result: Record<string, string> = {}
    if (!qs) return result
    if (qs.startsWith("#")) qs = qs.slice(1)
    const params = new URLSearchParams(qs)
    for (const key of params.keys()) {
        result[key] ??= params.getAll(key).join(";")
    }
    return result
}

/**
 * Encode an object into a query string with prefix
 * @example
 * qsEncode({ foo: "bar", baz: "qux", quux: undefined })
 * // => "?foo=bar&baz=qux"
 * qsEncode({})
 * // => ""
 * qsEncode({ hash: "value" }, "#")
 * // => "#hash=value"
 */
export const qsEncode = (
    obj: Record<string, string | string[] | undefined>,
    prefix = "?",
): string => {
    const params = new URLSearchParams()
    for (const [key, value] of Object.entries(obj)) {
        // Skip undefined values
        if (value === undefined) continue

        if (Array.isArray(value)) {
            for (const item of value) params.append(key, item)
        } else {
            params.set(key, value)
        }
    }
    const str = params.toString()
    return str ? `${prefix}${str}` : ""
}

export const updateSearchParams = (
    update: (searchParams: URLSearchParams) => void,
    mode: "replace" | "push" = "replace",
) => {
    const url = new URL(window.location.href)
    update(url.searchParams)

    if (mode === "replace") window.history.replaceState(null, "", url)
    else window.history.pushState(null, "", url)
}

/** Read a single query parameter from the current page URL. */
export const getSearchParam = (key: string) =>
    new URL(window.location.href).searchParams.get(key)
