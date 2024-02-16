import "./_types.js"

/**
 * Check if the given node is interesting
 * @param {OSMNode} node Node
 * @param {Set<string>} membersSet Set of all members in "n123" format
 * @returns {boolean} True if the node is interesting
 */
const isInterestingNode = (node, membersSet) => {
    if (node.type !== "node") {
        console.error(`Invalid node type: ${node.type}`)
        return true
    }

    const isMember = membersSet.has(`n${node.id}`)
    if (!isMember) return true

    const hasTags = node.tags.size > 0
    return hasTags
}

/**
 * Parse Format07 elements into a mapping to OSMObjects
 * @param {object[]} elements Format07 elements
 * @returns {{node: Map<number, OSMNode>, way: Map<number, OSMWay>, relation: Map<number, OSMRelation>}} Mapping to OSMObjects
 */
export const parseElements = (elements) => {
    // Create ref map for quick type+id lookup
    const refMap = {
        node: new Map(),
        way: new Map(),
        relation: new Map(),
    }

    for (const element of elements) {
        refMap[element.type].add(element.id, element)
    }

    // Set of all members in "n123" format (for filtering out boring nodes)
    const membersSet = new Set(
        [...refMap.way.values(), ...refMap.relation.values()].flatMap((object) =>
            object.members.map((member) => `${member.type[0]}${member.id}`),
        ),
    )

    const resultMap = {
        node: new Map(),
        way: new Map(),
        relation: new Map(),
    }

    /**
     * Util to resolve members by their ref
     * @param {object[]} members Members
     * @returns {OSMObject[]} Resolved members
     */
    const resolveMembers = (members) =>
        members
            .filter((ref) => ref.type !== "relation")
            .map((ref) => {
                const elementType = ref.type
                const elementId = ref.id
                const element = refMap[elementType].get(elementId)
                parseElement(element)
                return resultMap[elementType].get(elementId)
            })

    // Parse a Format07 element
    const parseElement = (element) => {
        const elementType = element.type
        const elementId = element.id

        // Don't parse the same element twice
        if (resultMap[elementType].has(elementId)) return

        if (elementType === "node") {
            const node = {
                type: elementType,
                id: elementId,
                version: element.version,
                tags: element.tags,
                lon: element.lon,
                lat: element.lat,
            }
            node.interesting = isInterestingNode(node, membersSet)
            resultMap[elementType].set(elementId, node)
        } else if (elementType === "way" || elementType === "relation") {
            resultMap[elementType].set(elementId, {
                type: elementType,
                id: elementId,
                version: element.version,
                tags: element.tags,
                members: resolveMembers(element.members),
            })
        } else {
            console.error(`Unsupported element type: ${elementType}`)
        }
    }

    // Parse all elements
    for (const type of Object.keys(refMap)) {
        for (const element of refMap[type].values()) {
            parseElement(element)
        }
    }

    return resultMap
}
