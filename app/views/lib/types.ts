import type { Status } from "@lib/proto/note_pb"

export type OSMDiffAction = "create" | "modify" | "delete"

export interface OSMNode {
  type: "node"
  id: bigint
  geom: [number, number]
  version?: bigint
  diffAction?: OSMDiffAction
}

export interface OSMWay {
  type: "way"
  id: bigint
  geom: [number, number][]
  version?: bigint
  area?: boolean
  diffAction?: OSMDiffAction
}

interface OSMRelation {
  type: "relation"
  id: bigint
  version?: bigint
}

export interface OSMNote {
  type: "note"
  id: bigint | null
  geom: [number, number]
  body: string
  status: Status
}

/** [minLon, minLat, maxLon, maxLat] */
export type Bounds = [number, number, number, number]

export interface OSMChangeset {
  type: "changeset"
  id: bigint
  bounds: Bounds[]
}

export type OSMObject = OSMNode | OSMWay | OSMRelation | OSMNote | OSMChangeset
