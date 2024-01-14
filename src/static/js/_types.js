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
 * @property {object} tags Object tags
 * @property {number} lon Object longitude
 * @property {number} lat Object latitude
 */

/**
 * @typedef {object} OSMWay
 * @property {"way"} type Object type
 * @property {number} id Object id
 * @property {string} version Object version
 * @property {object} tags Object tags
 * @property {OSMNode[]} nodes Object nodes
 */

/**
 * @typedef {object} OSMRelationMember
 * @property {string} type Member type, can be "node", "way", or "relation"
 * @property {number} ref Member reference
 * @property {string} role Member role
 */

/**
 * @typedef {object} OSMRelation
 * @property {"relation"} type Object type
 * @property {number} id Object id
 * @property {string} version Object version
 * @property {object} tags Object tags
 * @property {OSMRelationMember[]} members Object members
 */

/**
 * @typedef {object} OSMNote
 * @property {"note"} type Object type
 * @property {number} id Object id
 * @property {number} lon Object longitude
 * @property {number} lat Object latitude
 * @property {string} icon Icon theme
 */

/**
 * @typedef {object} OSMChangeset
 * @property {"changeset"} type Object type
 * @property {number} id Object id
 * @property {object} tags Object tags
 * @property {number[]|null} bounds Optional object bounds coordinates in the format [minLat, minLon, maxLat, maxLon]

/**
 * @typedef {OSMNode|OSMWay|OSMRelation|OSMNote|OSMChangeset} OSMObject
 */
