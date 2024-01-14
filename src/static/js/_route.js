/**
 * Escape a string for use in a regular expression.
 * Source: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Regular_expressions#escaping
 * @param {string} str String to escape
 * @returns {string} Escaped string
 * @example
 * escapeRegExWithoutRoundBrackets("foo.bar()")
 * // => "foo\.bar()"
 */
const escapeRegExWithoutRoundBrackets = (str) => str.replace(/[.*+?^${}|[\]\\]/g, "\\$&")

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
         * Execute load action on this route
         * @param {string} path Current path
         * @param {object} options Options to pass to action
         * @param {"init"|"event"|"script"} options.source Source of the load action
         * @returns {any} Action return value
         */
        load: (path, options) => {
            // Extract path parameters
            const pathParams = re.exec(path).map((param, i) => (i > 0 && param ? decodeURIComponent(param) : param))
            return controller.load(pathParams, options)
        },

        /**
         * Execute unload action on this route
         * @param {object} options Options to pass to action
         * @param {boolean} options.sameRoute Whether the new route is the same as the current route
         * @returns {any} Action return value
         */
        unload: (options) => {
            return controller.unload(options)
        },
    }
}
