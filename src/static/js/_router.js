import * as L from "leaflet"
import { encodeMapState, encodeMapStateEx, parseMapState, setMapState } from "./_map-utils.js"
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
 * @param {L.Map} map Leaflet map
 * @param {object} pathControllerMap Mapping of URL path templates to route controller objects
 */
export const Router = (map, pathControllerMap) => {
    const routes = Object.entries(pathControllerMap).map(([path, controller]) => Route(path, controller))
    console.debug(`Loaded ${routes.length} routes`)

    // Find the first route that matches a path
    const findRoute = (path) => routes.find((route) => route.match(path))

    let currentPath = removeTrailingSlash(location.pathname) + location.search
    let currentRoute = findRoute(currentPath)

    // On navigation (browser back/forward), load the route
    const onNavigation = () => {
        console.debug("onNavigation", location)
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

    // On hash change, update the map view
    const onHashChange = () => {
        // TODO: check if no double setMapState triggered
        console.debug("onHashChange", location.hash)
        let newState = parseMapState(location.hash)

        // Get the current state if empty/invalid and replace the hash
        if (!newState) {
            const encoded = encodeMapStateEx(map)
            newState = encoded.state
            history.replaceState(null, "", encoded.hash) // TODO: will this not remove path?
        }

        // Change the map view
        setMapState(map, newState)
    }

    // On map change, update the hash
    const onMapChange = () => {
        const hash = encodeMapState(map)
        console.debug("onMapChange", hash)
        history.replaceState(null, "", hash) // TODO: will this not remove path?
    }

    // Listen for events
    window.addEventListener("popstate", onNavigation)
    window.addEventListener("hashchange", onHashChange)
    map.addEventListener("zoomend moveend baselayerchange overlaylayerchange", onMapChange)

    // Initial load
    if (currentRoute) currentRoute.load(currentPath, { source: "init" })

    // Return Router object
    return {
        /**
         * Navigate to a path and return true if successful
         * @param {string} newPath Path to navigate to
         * @returns {void}
         * @example
         * router.navigate("/way/1234")
         * // => true
         */
        navigate: (newPath) => {
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
        },
    }
}
