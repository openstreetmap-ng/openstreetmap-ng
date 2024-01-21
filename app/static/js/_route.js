/**
 * Create a route object
 * @param {string} path Route path
 * @param {object} controller Controller object
 */
export const Route = (pattern, controller) => {
    // Ignore query string and require exact match
    const re = new RegExp(`^${pattern}($|\\?)`)

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
            const matchGroups = re.exec(path).groups
            return controller.load(matchGroups, options)
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
