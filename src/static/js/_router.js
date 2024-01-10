/*
Router implements pushState-based navigation for the main page and
other pages that use a sidebar+map based layout (export, search results,
history, and browse pages).

The router is initialized with a set of routes: a mapping of URL path templates
to route controller objects. Path templates can contain placeholders
(`/note/:id`) and optional segments (`/:type/:id(/history)`).

Route controller objects can define four methods that are called at defined
times during routing:

    * The `load` method is called by the router when a path which matches the
      route's path template is loaded via a normal full page load. It is passed
      as arguments the URL path plus any matching arguments for placeholders
      in the path template.

    * The `pushState` method is called when a page which matches the route's path
      template is loaded via pushState. It is passed the same arguments as `load`.

    * The `popState` method is called when returning to a previously
      pushState-loaded page via popState (i.e. browser back/forward buttons).

    * The `unload` method is called on the exiting route controller when navigating
      via pushState or popState to another route.

  Note that while `load` is not called by the router for pushState-based loads,
  it's frequently useful for route controllers to call it manually inside their
  definition of the `pushState` and `popState` methods.

  An instance of Router is assigned to `router`. To navigate to a new page
  via pushState, call `router.route`:

      router.route('/way/1234');

  If `route` is passed a path that matches one of the path templates, it performs
  the appropriate actions and returns true. Otherwise it returns false.

  Router also handles updating the hash portion of the URL containing transient
  map state such as the position and zoom level. Some route controllers may wish to
  temporarily suppress updating the hash (for example, to omit the hash on pages
  such as `/way/1234` unless the map is moved). This can be done by using
  `router.withoutMoveListener` to run a block of code that may update
  move the map without the hash changing.
*/

import { Route } from "./_route.js"
import { formatHash, parseHash } from "./_utils.js"

const removeTrailingSlash = (str) => (str.endsWith("/") && str.length > 1 ? str.slice(0, -1) : str)

const stripHash = (str) => {
    const i = str.indexOf("#")
    return i === -1 ? str : str.slice(0, i)
}

// Replace the current window.history state
const replaceState = (state) =>
    window.history.replaceState(state, document.title, state.center ? formatHash(state) : location)

export const Router = (map, pathControllerMap) => {
    const routes = Object.entries(pathControllerMap).map(([path, controller]) => Route(path, controller))

    console.debug(`Loaded ${routes.length} routes`)

    // Find the first route that matches a path
    const routesRecognize = (path) => routes.find((route) => route.match(path))

    let currentPath = removeTrailingSlash(location.pathname) + location.search
    let currentRoute = routesRecognize(currentPath)
    let currentHash = location.hash || formatHash(map)

    // On popstate (browser back/forward), replace the state
    const onWindowPopState = (e) => {
        // Is it a real popstate event or just a hash change?
        if (!e.originalEvent.state) return

        const path = removeTrailingSlash(location.pathname) + location.search

        // Skip if the path hasn't changed
        if (path === currentPath) return

        const newRoute = routesRecognize(path)

        // Unload the current route
        if (currentRoute) {
            const sameRoute = newRoute === currentRoute
            currentRoute.run("unload", null, sameRoute)
        }

        // Load the new route via popState action
        currentPath = path
        currentRoute = newRoute
        if (currentRoute) currentRoute.run("popState", currentPath)

        map.setState(e.originalEvent.state, { animate: false })
    }

    // On hash change, replace the state
    const onWindowHashChange = () => {
        const hash = location.hash
        console.debug("onWindowHashChange", hash)
        if (hash === currentHash) return

        const state = parseHash(hash)
        currentHash = hash
        replaceState(state)
        map.setState(state)
    }

    // On move, compute the current state and replace the state
    const onMapChange = () => {
        const hash = formatHash(map)
        console.debug("onMapChange", hash)
        if (hash === currentHash) return

        const state = parseHash(hash) // TODO: optimize unnecessary format+parse
        currentHash = hash
        replaceState(state)
    }

    // Listen for window and map events
    window.addEventListener("popstate", onWindowPopState)
    window.addEventListener("hashchange", onWindowHashChange)
    map.addEventListener("zoomend moveend baselayerchange overlaylayerchange", onMapChange)

    // Return Router object
    return {
        // Route to a path and return true if successful
        route: (path) => {
            const pathWithoutHash = stripHash(path)
            const newRoute = routesRecognize(pathWithoutHash)

            // No matching route
            if (!newRoute) return false

            // Unload the current route
            if (currentRoute) {
                const sameRoute = newRoute === currentRoute
                currentRoute.run("unload", null, sameRoute)
            }

            // Update browser history
            const state = formatHash(map)
            window.history.pushState(state, document.title, path)

            // Load the new route via pushState action
            currentPath = pathWithoutHash
            currentRoute = newRoute
            currentRoute.run("pushState", currentPath)

            return true
        },

        // Replace the state and path without "reloading" the page
        replaceStateFromPath: (path) => window.history.replaceState(parseHash(path), document.title, path),

        // Call load on the current route and replace the state
        load: () => {
            if (currentRoute) {
                const state = currentRoute.run("load", currentPath)
                replaceState(state || {})
            }
        },

        // Execute a callback without computing the new hash
        withoutMoveListener: (callback) => {
            const disableMoveListener = () => {
                map.removeEventListener("moveend", onMapChange)
                map.addOneTimeEventListener("moveend", () => {
                    map.addEventListener("moveend", onMapChange)
                })
            }

            map.addOneTimeEventListener("movestart", disableMoveListener)
            callback()
            map.removeEventListener("movestart", disableMoveListener)
        },
    }
}
