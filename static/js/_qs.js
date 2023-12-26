// Parse a query string into an object
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

// Stringify an object into a query string
export const qsStringify = (obj) => {
    const params = new URLSearchParams()

    for (const [key, value] of Object.entries(obj)) {
        if (Array.isArray(value)) {
            for (const item of value) params.append(key, item)
        } else {
            params.set(key, value)
        }
    }

    return params.toString()
}
