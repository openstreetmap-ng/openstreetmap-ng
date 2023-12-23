import QueryString from 'qs'

// Compute the coordinate precision for a given zoom level
export const zoomPrecision = zoom => Math.max(0, Math.ceil(Math.log(zoom) / Math.LN2))

// Create a hash string for a state
// Accepts either a map object or an object with the following properties:
//   center: L.LatLng
//   zoom: number
//   layers: string
// Returns a string like "#map=15/51.505/-0.09&layers=BT"
export const formatHash = args => {
    let center, zoom, layers

    if (args instanceof L.Map) {
        center = args.getCenter()
        zoom = args.getZoom()
        layers = args.getLayersCode()
    } else {
        center = args.center || L.latLng(args.lat, args.lon)
        zoom = args.zoom
        layers = args.layers || ''
    }

    center = center.wrap()
    layers = layers.replace('M', '') // Standard layer is the default (implicit)

    const precision = zoomPrecision(zoom)

    let hash = `#map=${zoom}/${center.lat.toFixed(precision)}/${center.lng.toFixed(precision)}`

    if (layers)
        hash += `&layers=${layers}`

    return hash
}

// Parse a hash string into a state
export const parseHash = hash => {
    const args = {}

    // Skip if there's no hash
    const i = hash.indexOf('#')
    if (i < 0)
        return args

    // Parse the hash as a query string
    const params = QueryString.parse(hash.slice(i + 1))

    // Assign map state only if present and length is 3
    if (params.map) {
        const components = params.map.split('/')
        if (components.length === 3) {

            args.zoom = parseInt(components[0], 10)

            // Assign position only if it's valid
            const lat = parseFloat(components[1])
            const lon = parseFloat(components[2])
            if (!isNaN(lat) && !isNaN(lon))
                args.center = new L.LatLng(lat, lon)

        }
    }

    // Assign layers only if present
    if (params.layers)
        args.layers = params.layers

    return args
}
