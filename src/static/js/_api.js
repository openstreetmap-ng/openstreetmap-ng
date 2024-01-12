import { apiUrl } from "./_params.js"

export const getObjectRequestUrl = (object) => {
    const type = object.type === "note" ? "notes" : object.type

    // When requested for complex object, request for full version (incl. object's members)
    // Ignore version specification as there is a very high chance it will be rendered incorrectly
    if (type === "way" || type === "relation") {
        return `${apiUrl}/api/0.6/${type}/${object.id}/full`
    }

    if (object.version) {
        return `${apiUrl}/api/0.6/${type}/${object.id}/${object.version}`
    }

    return `${apiUrl}/api/0.6/${type}/${object.id}`
}
