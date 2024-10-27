export interface OSMNode {
    type: "node"
    id: number
    geom: [number, number] // lat, lon
    version?: number
}

export interface OSMWay {
    type: "way"
    id: number
    geom: [number, number][] // [[lat, lon], ...]
    version?: number
    area?: boolean
}

export interface OSMRelation {
    type: "relation"
    id: number
    version?: number
}

export interface OSMNote {
    type: "note"
    id: number
    lon: number
    lat: number
    icon: string
    draggable?: boolean
    interactive?: boolean
}

export type Bounds = [number, number, number, number]

export interface OSMChangeset {
    type: "changeset"
    id: number
    bounds: Bounds[] // [[minLon, minLat, maxLon, maxLat], ...]
}

export type OSMObject = OSMNode | OSMWay | OSMRelation | OSMNote | OSMChangeset

// /**
//  * @typedef {object} RoutingStep
//  * @property {number} lon Begin longitude
//  * @property {number} lat Begin latitude
//  * @property {L.Polyline} line Line segment
//  * @property {number} distance Distance in meters
//  * @property {number} time Time in seconds
//  * @property {number} code Instruction code
//  * @property {string} text Instruction text
//  */

// /**
//  * @typedef {object} RoutingRoute
//  * @property {RoutingStep[]} steps Routing steps
//  * @property {text} attribution Routing engine attribution (HTML)
//  * @property {number|null} ascend Optional ascend in meters
//  * @property {number|null} descend Optional descend in meters
//  */
