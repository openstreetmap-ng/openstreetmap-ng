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
