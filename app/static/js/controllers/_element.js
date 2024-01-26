import * as L from "leaflet"
import { getPageTitle } from "../_title.js"
import { focusManyMapObjects, focusMapObject } from "../leaflet/_forus-layer.js"
import { isInterestingNode } from "../leaflet/_layers.js"
import { getBaseFetchController } from "./_base_fetch.js"

/**
 * Create a new element controller
 * @param {L.Map} map Leaflet map
 * @returns {object} Controller
 */
export const getElementController = (map) => {
    const onLoaded = (sidebarContent) => {
        // Get elements
        const sidebarTitleElement = sidebarContent.querySelector(".sidebar-title")
        const sidebarTitle = sidebarTitleElement.textContent
        // TODO: (version X) in title

        // Set page title
        document.title = getPageTitle(sidebarTitle)

        // Get params
        const params = JSON.parse(sidebarTitleElement.dataset.params)
        const mainElementType = params.type
        const mainElementId = params.id
        const elements = params.elements

        // Not all elements are focusable (e.g., non-latest ways and relations)
        if (elements.length) {
            // Initialize ref map for quick lookup
            const refMap = {
                node: new Map(),
                way: new Map(),
                relation: new Map(),
            }

            for (const element of elements) {
                refMap[element.type].set(element.id, element)
            }

            // Resolve members by their ref
            const resolveMembers = (members) => [...members].map((ref) => refMap[ref.type].get(ref.id))

            // Set of all members in "n123" format
            const membersSet = new Set(
                [...refMap.way.values(), ...refMap.relation.values()].flatMap((object) =>
                    object.members.map((member) => `${member.type[0]}${member.id}`),
                ),
            )

            // Set of all parsed elements in "n123" format
            const parsedElementsSet = new Set()

            /**
             * Parse a simple OSMObject representation into a list of valid OSMObjects
             * @param {OSMObject|object} element Simple OSMObject representation
             * @returns {OSMObject[]} List of OSMObjects
             */
            const parseElement = (element) => {
                const elementType = element.type
                const elementId = element.id

                // Prevent infinite recursion and duplicate elements
                const elementKey = `${elementType[0]}${elementId}`
                if (parsedElementsSet.has(elementKey)) return []
                parsedElementsSet.add(elementKey)

                if (elementType === "node") {
                    const tags = element.tags
                    const lon = element.lon
                    const lat = element.lat

                    const node = {
                        type: elementType,
                        id: elementId,
                        version: 0, // currently unused
                        tags: tags,
                        lon: lon,
                        lat: lat,
                    }

                    // Filter out boring nodes
                    return isInterestingNode(node, membersSet) ? [node] : []
                }
                if (elementType === "way") {
                    const tags = element.tags
                    const members = resolveMembers(element.members)
                    return [
                        {
                            type: elementType,
                            id: elementId,
                            version: 0, // currently unused
                            tags: tags,
                            members: members,
                        },
                        ...members.flatMap((member) => parseElement(member)),
                    ]
                }
                if (elementType === "relation") {
                    const members = resolveMembers(element.members)
                    return members.flatMap((member) => parseElement(member))
                }

                console.error(`Unsupported element type: ${elementType}`)
                return []
            }

            const mainElement = refMap[mainElementType].get(mainElementId)
            const parsedElements = parseElement(mainElement)

            if (parsedElements.length) {
                const layers = focusManyMapObjects(map, parsedElements)

                // Get union bounds
                const layersBounds = layers.reduce((bounds, layer) => {
                    return bounds !== null ? bounds.extend(layer.getBounds()) : layer.getBounds()
                }, null)

                // Focus on the elements if they're offscreen
                if (!map.getBounds().contains(layersBounds)) {
                    map.fitBounds(layersBounds, { animate: false })
                }
            }
        }
    }

    const base = getBaseFetchController("element", onLoaded)
    const baseLoad = base.load
    const baseUnload = base.unload

    base.load = ({ type, id, version }) => {
        const url = `/api/web/partial/element/${type}/${id}${version ? `/${version}` : ""}`
        baseLoad({ url })
    }

    base.unload = () => {
        focusMapObject(map, null)
        baseUnload()
    }

    return base
}
