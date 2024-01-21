import { Route } from "./_route.js"
import "./_types.js"

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
 * Create a router object
 * @param {Map<string, object>} pathControllerMap Mapping of path regex patterns to controller objects
 */
export const Router = (pathControllerMap) => {
    const routes = [...pathControllerMap.entries()].map(([path, controller]) => Route(path, controller))
    console.debug(`Loaded ${routes.length} routes`)

    // Find the first route that matches a path
    const findRoute = (path) => routes.find((route) => route.match(path))

    let currentPath = removeTrailingSlash(location.pathname) + location.search
    let currentRoute = findRoute(currentPath)

    /**
     * Navigate to a path and return true if successful
     * @param {string} newPath Path to navigate to
     * @returns {void}
     * @example
     * router.navigate("/way/1234")
     * // => true
     */
    const navigate = (newPath) => {
        const newRoute = findRoute(newPath)
        if (!newRoute) throw new Error(`No route found for path: ${newPath}`)

        // Unload the current route
        if (currentRoute) currentRoute.unload({ sameRoute: newRoute === currentRoute })

        // Push the new history state
        history.pushState(null, "", newPath + location.hash)

        // Load the new route
        currentPath = newPath
        currentRoute = newRoute
        currentRoute.load(currentPath, { source: "script" })
    }

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
     * @param {PointerEvent} event Click event
     * @returns {void}
     */
    const onClick = (event) => {
        // Skip if default prevented
        if (event.defaultPrevented) return

        // Skip if not left click or modified click
        if (event.button !== 1 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return

        // Skip if target is not an anchor
        const target = event.target
        if (target.tagName !== "A") return

        // Skip if the anchor is not a link
        const href = target.getAttribute("href")
        if (!href) return

        // Skip if cross-protocol or cross-origin
        if (location.protocol !== target.protocol || location.host !== target.host) return

        // Attempt to navigate and prevent default if successful
        const newPath = removeTrailingSlash(target.pathname) + target.search
        if (navigate(newPath)) {
            event.preventDefault()
        }
    }

    // Listen for events
    window.addEventListener("popstate", onBrowserNavigation)
    window.addEventListener("click", onClick)

    // Initial load
    if (currentRoute) currentRoute.load(currentPath, { source: "init" })

    // Return Router object
    return { navigate }
}
