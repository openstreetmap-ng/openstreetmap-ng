import type { IndexController } from "./_router"

export interface Route {
    match: (path: string) => boolean
    load: (path: string) => void
    unload: () => void
}

/** Create a route object */
export const makeRoute = (pattern: string, controller: IndexController): Route => {
    // Ignore query string and require exact match
    const re = new RegExp(`^${pattern}($|\\?)`)

    return {
        /** Test if a path matches this route */
        match: (path: string): boolean => re.test(path),

        /** Execute load action on this route */
        load: (path: string): void => {
            // Extract path parameters
            const matchGroups = re.exec(path).groups
            controller.load(matchGroups)
        },

        /** Execute unload action on this route */
        unload: controller.unload,
    }
}
