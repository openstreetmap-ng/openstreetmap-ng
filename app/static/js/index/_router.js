import "../_types.js"
import { Route } from "./_route.js"

let routes
let currentPath
let currentRoute

// Find the first route that matches a path
const findRoute = (path) => routes.find((route) => route.match(path))

/**
 * Remove trailing slash from a string
 * @param {string} str Input string
 * @returns {string} String without trailing slash
 * @example
 * removeTrailingSlash("/way/1234/")
 * // => "/way/1234"
 */
const removeTrailingSlash = (str) => (str.endsWith("/") && str.length > 1 ? removeTrailingSlash(str.slice(0, -1)) : str)

/**
 * Navigate to a path, throwing an error if no route is found
 * @param {string} newPath Path to navigate to, including search
 * @returns {void}
 * @example
 * routerNavigateStrict("/way/1234")
 */
export const routerNavigateStrict = (newPath) => {
    console.debug("routerNavigateStrict", newPath)

    if (!routerNavigate(newPath)) {
        throw new Error(`No route found for path: ${newPath}`)
    }
}

/**
 * Navigate to a path and return true if successful
 * @param {string} newPath Path to navigate to, including search
 * @returns {boolean}
 * @example
 * routerNavigate("/way/1234")
 * // => true
 */
export const routerNavigate = (newPath) => {
    console.debug("routerNavigate", newPath)

    const newRoute = findRoute(newPath)
    if (!newRoute) return false

    // Unload the current route
    if (currentRoute) currentRoute.unload({ sameRoute: newRoute === currentRoute })

    // Push the new history state
    history.pushState(null, "", newPath + location.hash)

    // Load the new route
    currentPath = newPath
    currentRoute = newRoute
    currentRoute.load(currentPath, { source: "script" })
    return true
}

/**
 * Configure the router
 * @param {Map<string, object>} pathControllerMap Mapping of path regex patterns to controller objects
 */
export const configureRouter = (pathControllerMap) => {
    routes = Array.from(pathControllerMap).map(([path, controller]) => Route(path, controller))
    console.debug("Loaded", routes.length, "routes")

    currentPath = removeTrailingSlash(location.pathname) + location.search
    currentRoute = findRoute(currentPath)

    /**
     * Handle browser navigation events
     * @returns {void}
     */
    const onBrowserNavigation = () => {
        console.debug("onBrowserNavigation", location)
        const newPath = removeTrailingSlash(location.pathname) + location.search

        // Skip if the path hasn't changed
        if (newPath === currentPath) return

        const newRoute = findRoute(newPath)

        // Unload the current route
        if (currentRoute) currentRoute.unload({ sameRoute: newRoute === currentRoute })

        // Load the new route
        currentPath = newPath
        currentRoute = newRoute
        if (currentRoute) currentRoute.load(currentPath, { source: "event" })
    }

    /**
     * Attempt to navigate to the href of an anchor element
     * @param {MouseEvent} event Click event
     * @returns {void}
     */
    const onWindowClick = (event) => {
        // Skip if default prevented
        if (event.defaultPrevented) return

        // Skip if not left click or modified click
        if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return

        // Skip if target is not an anchor
        const target = event.target.closest("a")
        if (!target) return

        // Skip if the anchor is not a link
        if (!target.href) return

        // Skip if cross-protocol or cross-origin
        if (location.protocol !== target.protocol || location.host !== target.host) return

        // Attempt to navigate and prevent default if successful
        const newPath = removeTrailingSlash(target.pathname) + target.search
        console.debug("onWindowClick", newPath)

        if (routerNavigate(newPath)) {
            event.preventDefault()
        }
    }

    // Listen for events
    window.addEventListener("popstate", onBrowserNavigation)
    window.addEventListener("click", onWindowClick)

    // Initial load
    if (currentRoute) currentRoute.load(currentPath, { source: "init" })
}
