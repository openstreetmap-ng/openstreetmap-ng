/**
 * Parse a query string into an object
 * @param {string} qs Query string
 * @returns {object} Object with query string parameters
 * @example
 * qsParse("foo=bar&baz=qux")
 * // => { foo: "bar", baz: "qux" }
 */
export const qsParse = (qs) => {
    const params = new URLSearchParams(qs)
    const result = {}

    for (const [key, value] of params.entries()) {
        if (key in result) {
            if (Array.isArray(result[key])) {
                result[key].push(value)
            } else {
                result[key] = [result[key], value]
            }
        } else {
            result[key] = value
        }
    }

    return result
}

/**
 * Stringify an object into a query string
 * @param {object} obj Object to stringify
 * @returns {string} Query string
 * @example
 * qsStringify({ foo: "bar", baz: "qux" })
 * // => "foo=bar&baz=qux"
 */
export const qsStringify = (obj) => qsEncode(obj).toString()

/**
 * Encode an object into a URLSearchParams object
 * @param {object} obj Object to encode
 * @returns {URLSearchParams} Encoded query string
 * @example
 * qsEncode({ foo: "bar", baz: "qux" })
 * // => URLSearchParams { "foo" => "bar", "baz" => "qux" }
 */
export const qsEncode = (obj) => {
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

    return params
}
