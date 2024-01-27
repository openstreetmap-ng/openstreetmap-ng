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
 * @property {string} version Object version
 * @property {Map<string, string>} tags Object tags
 * @property {number} lon Object longitude
 * @property {number} lat Object latitude
 * @property {string|undefined} role Optional member role
 * @property {boolean|undefined} interesting Optional interesting flag for the renderer
 */

/**
 * @typedef {object} OSMWay
 * @property {"way"} type Object type
 * @property {number} id Object id
 * @property {string} version Object version
 * @property {Map<string, string>} tags Object tags
 * @property {OSMNode[]} members Object members (nodes)
 * @property {string|undefined} role Optional member role
 */

/**
 * @typedef {object} OSMRelation
 * @property {"relation"} type Object type
 * @property {number} id Object id
 * @property {string} version Object version
 * @property {Map<string, string>} tags Object tags
 * @property {OSMNode[]|OSMWay[]|OSMRelation[]} members Object members
 * @property {string|undefined} role Optional member role
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
 * @property {Map<string, string>} tags Object tags
 * @property {number[]|null} bounds Optional object bounds coordinates in the format [minLat, minLon, maxLat, maxLon]

/**
 * @typedef {OSMNode|OSMWay|OSMRelation|OSMNote|OSMChangeset} OSMObject
 */
