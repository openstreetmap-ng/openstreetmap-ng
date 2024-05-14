import "./_types.js"

/**
 * Check if the given node is interesting
 * @param {OSMNode} node Node
 * @param {Set<number>} wayMembersSet Set of all members in "n123" format
 * @returns {boolean} True if the node is interesting
 */
const isInterestingNode = (node, wayMembersSet) => {
    const isMember = wayMembersSet.has(node.id)
    return !isMember
    // if (!isMember) return true
    // const hasTags = node.tags.size > 0
    // return hasTags
}

/**
 * Parse Format07 elements into a mapping to OSMObjects
 * @param {object[]} elements Format07 elements
 * @returns {{node: Map<number, OSMNode>, way: Map<number, OSMWay>, relation: Map<number, OSMRelation>}} Mapping to OSMObjects
 */
export const parseElements = (elements) => {
    console.debug("parseElements", elements.length)

    // Create ref map for quick type+id lookup
    const refMap = {
        node: new Map(),
        way: new Map(),
        relation: new Map(),
    }

    for (const element of elements) {
        refMap[element.type].set(element.id, element)
    }

    // Set of all way members ids
    const wayMembersSet = new Set()
    for (const way of refMap.way.values()) {
        for (const member of way.members) {
            wayMembersSet.add(member.id)
        }
    }

    const result = {
        node: new Map(),
        way: new Map(),
        relation: new Map(),
    }

    /**
     * Util to resolve members by their ref
     * @param {object[]} members Members
     * @returns {OSMObject[]} Resolved members
     */
    const resolveMembers = (members) => {
        const resolved = []
        for (const ref of members) {
            if (ref.type === "relation") continue  // Skip nested relations
            const elementType = ref.type
            const elementId = ref.id
            const element = refMap[elementType].get(elementId)
            if (element) {
                processElement(element)
                resolved.push(result[elementType].get(elementId))
            } else {
                console.warn("Missing", elementType, elementId)
            }
        }
        return resolved
    }

    // Process an element and store the result
    const processElement = (element) => {
        const elementType = element.type
        const elementId = element.id

        // Skip parsing the same element repeatedly
        if (result[elementType].has(elementId)) return

        if (elementType === "node") {
            const node = {
                type: elementType,
                id: elementId,
                version: element.version,
                lon: element.lon,
                lat: element.lat,
                tags: new Map(Object.entries(element.tags)),
            }
            node.interesting = isInterestingNode(node, wayMembersSet)
            result[elementType].set(elementId, node)
        } else if (elementType === "way" || elementType === "relation") {
            result[elementType].set(elementId, {
                type: elementType,
                id: elementId,
                version: element.version,
                tags: new Map(Object.entries(element.tags)),
                members: resolveMembers(element.members),
            })
        } else {
            console.error("Unsupported element type", elementType)
        }
    }

    // Process all elements
    for (const type of Object.keys(refMap)) {
        for (const element of refMap[type].values()) {
            processElement(element)
        }
    }

    return result
}
