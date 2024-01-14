/**
 * Escape a string for use in a regular expression.
 * Source: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Regular_expressions#escaping
 * @param {string} str String to escape
 * @returns {string} Escaped string
 * @example
 * escapeRegExWithoutRoundBrackets("foo.bar")
 * // => "foo\.bar"
 */
const escapeRegExWithoutRoundBrackets = (str) => str.replace(/[.*+?^${}|[\]\\]/g, "\\$&")

// TODO: Controller type
/**
 * Create a route object
 * @param {string} path Route path
 * @param {object} controller Controller object
 */
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
        /**
         * Test if a path matches this route
         * @param {string} path Path to test
         * @returns {boolean} True if path matches this route
         */
        match: (path) => re.test(path),

        /**
         * Run action on this route
         * @param {string} action Action to run
         * @param {string} path Current path
         * @param {...any} args Action arguments
         * @returns {any} Action return value
         */
        run: (action, path, ...args) => {
            // Extract path parameters
            const pathParams = re.exec(path).map((param, i) => (i > 0 && param ? decodeURIComponent(param) : param))

            return controller[action](...pathParams, ...args)
        },
    }
}
