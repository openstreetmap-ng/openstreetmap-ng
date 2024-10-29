/*
 * Leaflet.locationfilter - leaflet location filter plugin
 * Copyright (C) 2012, Tripbirds.com, http://tripbirds.com
 * https://github.com/kajic/leaflet-locationfilter
 * Originally licensed under the MIT License.
 * Modification licensed under the Unlicense <https://unlicense.org/>.
 */
// @ts-nocheck
import * as L from "leaflet"

L.LatLngBounds.prototype.modify = function (map, amount) {
    let sw = this.getSouthWest()
    let ne = this.getNorthEast()
    const swPoint = map.latLngToLayerPoint(sw)
    const nePoint = map.latLngToLayerPoint(ne)

    sw = map.layerPointToLatLng(new L.Point(swPoint.x - amount, swPoint.y + amount))
    ne = map.layerPointToLatLng(new L.Point(nePoint.x + amount, nePoint.y - amount))

    return new L.LatLngBounds(sw, ne)
}

const LocationFilter = L.Layer.extend({
    includes: L.Evented,

    options: {},

    initialize: function (options) {
        L.Util.setOptions(this, options)
    },

    addTo: function (map) {
        map.addLayer(this)
        return this
    },

    onAdd: function (map) {
        this._map = map
    },

    onRemove: function (map) {
        this.disable()
    },

    /* Get the current filter bounds */
    getBounds: function () {
        return new L.LatLngBounds(this._sw, this._ne)
    },

    setBounds: function (bounds) {
        this._nw = bounds.getNorthWest()
        this._ne = bounds.getNorthEast()
        this._sw = bounds.getSouthWest()
        this._se = bounds.getSouthEast()
        if (this.isEnabled()) {
            this._draw()
            this.fire("change", { bounds: bounds })
        }
    },

    isEnabled: function () {
        return this._enabled
    },

    /* Draw a rectangle */
    _drawRectangle: function (bounds, options) {
        const defaultOptions = {
            stroke: false,
            fill: true,
            fillColor: "black",
            fillOpacity: 0.3,
            smoothFactor: 0,
            interactive: false,
        }
        const mergedOptions = options ? L.Util.extend(defaultOptions, options) : defaultOptions
        const rect = new L.Rectangle(bounds, mergedOptions)
        rect.addTo(this._layer)
        return rect
    },

    /* Draw a draggable marker */
    _drawImageMarker: function (point, options) {
        const marker = new L.Marker(point, {
            icon: new L.icon({
                iconUrl: options.iconUrl,
                iconAnchor: options.anchor,
                iconSize: options.size,
                className: options.className,
            }),
            draggable: true,
        })
        marker.addTo(this._layer)
        return marker
    },

    /* Draw a move marker. Sets up drag listener that updates the
       filter corners and redraws the filter when the move marker is
       moved */
    _drawMoveMarker: function (point) {
        this._moveMarker = this._drawImageMarker(point, {
            iconUrl: "/static/img/location-filter/move-handle.webp",
            className: "location-filter move-marker",
        })
        this._moveMarker.on("drag", () => {
            const markerPos = this._moveMarker.getLatLng()
            const latDelta = markerPos.lat - this._nw.lat
            const lngDelta = markerPos.lng - this._nw.lng
            this._nw = new L.LatLng(this._nw.lat + latDelta, this._nw.lng + lngDelta, true)
            this._ne = new L.LatLng(this._ne.lat + latDelta, this._ne.lng + lngDelta, true)
            this._sw = new L.LatLng(this._sw.lat + latDelta, this._sw.lng + lngDelta, true)
            this._se = new L.LatLng(this._se.lat + latDelta, this._se.lng + lngDelta, true)
            this._draw()
        })
        this._setupDragendListener(this._moveMarker)
        return this._moveMarker
    },

    /* Draw a resize marker */
    _drawResizeMarker: function (point, latFollower, lngFollower, otherPos) {
        return this._drawImageMarker(point, {
            iconUrl: "/static/img/location-filter/resize-handle.webp",
            className: "location-filter resize-marker",
        })
    },

    /* Track moving of the given resize marker and update the markers
       given in options.moveAlong to match the position of the moved
       marker. Update filter corners and redraw the filter */
    _setupResizeMarkerTracking: function (marker, options) {
        marker.on("drag", () => {
            const curPosition = marker.getLatLng()
            const latMarker = options.moveAlong.lat
            const lngMarker = options.moveAlong.lng
            // Move follower markers when this marker is moved
            latMarker.setLatLng(new L.LatLng(curPosition.lat, latMarker.getLatLng().lng, true))
            lngMarker.setLatLng(new L.LatLng(lngMarker.getLatLng().lat, curPosition.lng, true))
            // Sort marker positions in nw, ne, sw, se order
            const corners = [
                this._nwMarker.getLatLng(),
                this._neMarker.getLatLng(),
                this._swMarker.getLatLng(),
                this._seMarker.getLatLng(),
            ] as const
            corners.sort((a, b) => {
                if (a.lat !== b.lat) return b.lat - a.lat
                return a.lng - b.lng
            })
            // Update corner points and redraw everything except the resize markers
            this._nw = corners[0]
            this._ne = corners[1]
            this._sw = corners[2]
            this._se = corners[3]
            this._draw({ repositionResizeMarkers: false })
        })
        this._setupDragendListener(marker)
    },

    /* Emit a change event whenever dragend is triggered on the
       given marker */
    _setupDragendListener: function (marker) {
        marker.on("dragend", () => {
            this.fire("change", { bounds: this.getBounds() })
        })
    },

    /* Create bounds for the mask rectangles and the location
       filter rectangle */
    _calculateBounds: function () {
        const mapBounds = this._map.getBounds()
        const sw = mapBounds.getSouthWest()
        const ne = mapBounds.getNorthEast()

        // Bounds for the mask rectangles
        this._northBounds = new L.LatLngBounds(new L.LatLng(this._ne.lat, sw.lng), ne)
        this._westBounds = new L.LatLngBounds(new L.LatLng(this._sw.lat, sw.lng), this._nw)
        this._eastBounds = new L.LatLngBounds(this._se, new L.LatLng(this._ne.lat, ne.lng))
        this._southBounds = new L.LatLngBounds(sw, new L.LatLng(this._sw.lat, ne.lng))
    },

    /* Initializes rectangles and markers */
    _initialDraw: function () {
        if (this._initialDrawCalled) return

        this._layer = new L.LayerGroup()

        // Calculate filter bounds
        this._calculateBounds()

        // Create rectangles
        this._northRect = this._drawRectangle(this._northBounds)
        this._westRect = this._drawRectangle(this._westBounds)
        this._eastRect = this._drawRectangle(this._eastBounds)
        this._southRect = this._drawRectangle(this._southBounds)
        this._innerRect = this._drawRectangle(this.getBounds(), {
            stroke: true,
            color: "white",
            weight: 1,
            opacity: 0.9,
            fillOpacity: 0,
        })

        // Create resize markers
        this._nwMarker = this._drawResizeMarker(this._nw)
        this._neMarker = this._drawResizeMarker(this._ne)
        this._swMarker = this._drawResizeMarker(this._sw)
        this._seMarker = this._drawResizeMarker(this._se)

        // Setup tracking of resize markers. Each marker has pair of
        // follower markers that must be moved whenever the marker is
        // moved. For example, whenever the north west resize marker
        // moves, the south west marker must move along on the x-axis
        // and the north east marker must move on the y axis
        this._setupResizeMarkerTracking(this._nwMarker, { moveAlong: { lat: this._neMarker, lng: this._swMarker } })
        this._setupResizeMarkerTracking(this._neMarker, { moveAlong: { lat: this._nwMarker, lng: this._seMarker } })
        this._setupResizeMarkerTracking(this._swMarker, { moveAlong: { lat: this._seMarker, lng: this._nwMarker } })
        this._setupResizeMarkerTracking(this._seMarker, { moveAlong: { lat: this._swMarker, lng: this._neMarker } })

        // Create move marker
        this._moveMarker = this._drawMoveMarker(this._nw)

        this._initialDrawCalled = true
    },

    /* Reposition all rectangles and markers to the current filter bounds. */
    _draw: function (options) {
        const repositionResizeMarkers = options?.repositionResizeMarkers ?? true

        // Calculate filter bounds
        this._calculateBounds()

        // Reposition rectangles
        this._northRect.setBounds(this._northBounds)
        this._westRect.setBounds(this._westBounds)
        this._eastRect.setBounds(this._eastBounds)
        this._southRect.setBounds(this._southBounds)
        this._innerRect.setBounds(this.getBounds())

        // Reposition resize markers
        if (repositionResizeMarkers) {
            this._nwMarker.setLatLng(this._nw)
            this._neMarker.setLatLng(this._ne)
            this._swMarker.setLatLng(this._sw)
            this._seMarker.setLatLng(this._se)
        }

        // Reposition the move marker
        this._moveMarker.setLatLng(this._nw)
    },

    /* Adjust the location filter to the current map bounds */
    _adjustToMap: function () {
        this.setBounds(this._map.getBounds())
        this._map.zoomOut()
    },

    /* Enable the location filter */
    enable: function () {
        if (this._enabled) {
            return
        }

        // Initialize corners
        let bounds: any
        if (this._sw && this._ne) {
            bounds = new L.LatLngBounds(this._sw, this._ne)
        } else if (this.options.bounds) {
            bounds = this.options.bounds
        } else {
            bounds = this._map.getBounds()
        }
        this._map.invalidateSize()
        this._nw = bounds.getNorthWest()
        this._ne = bounds.getNorthEast()
        this._sw = bounds.getSouthWest()
        this._se = bounds.getSouthEast()

        // Draw filter
        this._initialDraw()
        this._draw()

        // Set up map move event listener
        this._moveHandler = () => {
            this._draw()
        }
        this._map.on("move", this._moveHandler)

        // Add the filter layer to the map
        this._layer.addTo(this._map)

        // Zoom out the map if necessary
        const mapBounds = this._map.getBounds()
        bounds = new L.LatLngBounds(this._sw, this._ne).modify(this._map, 10)
        if (!(mapBounds.contains(bounds.getSouthWest()) && mapBounds.contains(bounds.getNorthEast()))) {
            this._map.fitBounds(bounds)
        }

        this._enabled = true

        // Fire the enabled event
        this.fire("enabled")
    },

    /* Disable the location filter */
    disable: function () {
        if (!this._enabled) {
            return
        }

        // Remove event listener
        this._map.off("move", this._moveHandler)

        // Remove rectangle layer from map
        this._map.removeLayer(this._layer)

        this._enabled = false

        // Fire the disabled event
        this.fire("disabled")
    },
})

export const getLocationFilter = () => new LocationFilter()
