/**
 * @typedef {object} MapState
 * @property {number} lon Map center longitude
 * @property {number} lat Map center latitude
 * @property {number} zoom Map zoom level
 * @property {string} layersCode Map layers code
 */

/**
 * @typedef {object} OSMNode
 * @property {"node"} type Object type
 * @property {number} id Object id
 * @property {number[]} geom Object geometry [lat, lon]
 */

/**
 * @typedef {object} OSMWay
 * @property {"way"} type Object type
 * @property {number} id Object id
 * @property {number[][]} geom Object geometry [[lat, lon], ...]
 */

/**
 * @typedef {object} OSMRelation
 * @property {"relation"} type Object type
 * @property {number} id Object id
 */

/**
 * @typedef {object} OSMNote
 * @property {"note"} type Object type
 * @property {number} id Object id
 * @property {number} lon Object longitude
 * @property {number} lat Object latitude
 * @property {string} icon Marker icon name
 * @property {boolean|undefined} draggable Optional draggable flag for the marker
 * @property {boolean|undefined} interactive Optional interactive flag for the marker
 */

/**
 * @typedef {object} OSMChangeset
 * @property {"changeset"} type Object type
 * @property {number} id Object id
 * @property {number[][]|null} bounds Optional object bounds coordinates in the format [[minLon, minLat, maxLon, maxLat], ...]

/**
 * @typedef {OSMNode|OSMWay|OSMRelation|OSMNote|OSMChangeset} OSMObject
 */

/**
 * @typedef {object} RoutingStep
 * @property {number} lon Begin longitude
 * @property {number} lat Begin latitude
 * @property {L.Polyline} line Line segment
 * @property {number} distance Distance in meters
 * @property {number} time Time in seconds
 * @property {number} code Instruction code
 * @property {string} text Instruction text
 */

/**
 * @typedef {object} RoutingRoute
 * @property {RoutingStep[]} steps Routing steps
 * @property {text} attribution Routing engine attribution (HTML)
 * @property {number|null} ascend Optional ascend in meters
 * @property {number|null} descend Optional descend in meters
 */
