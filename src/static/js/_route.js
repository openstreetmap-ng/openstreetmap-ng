// Source: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Regular_expressions#escaping
const escapeRegExWithoutRoundBrackets = (str) => str.replace(/[.*+?^${}|[\]\\]/g, "\\$&")

export const Route = (path, controller) => {
    const re = new RegExp(
        // biome-ignore lint/style/useTemplate: String concatenation for readability
        "^" +
            escapeRegExWithoutRoundBrackets(path)
                .replace(/\((.*?)\)/g, "(?:$1)?") // make (segments) optional
                .replace(/:\w+/g, "([^/]+)") + // make :placeholders match any sequence
            "(?:\\?.*)?$", // ignore query string
    )

    // Return Route object
    return {
        // Test if a path matches this route
        match: (path) => re.test(path),

        // Run action on this route
        run: (action, path, ...args) => {
            // Extract path parameters
            const pathParams = re.exec(path).map((param, i) => (i > 0 && param ? decodeURIComponent(param) : param))

            return controller[action](...pathParams, ...args)
        },
    }
}
