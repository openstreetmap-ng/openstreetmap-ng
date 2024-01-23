/*
 * Leaflet.locationfilter - leaflet location filter plugin
 * Copyright (C) 2012, Tripbirds.com, http://tripbirds.com
 * https://github.com/kajic/leaflet-locationfilter
 * Originally licensed under the MIT License.
 * Modification licensed under the AGPL-3.0 License.
 */
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

L.Control.Button = L.Class.extend({
    initialize: function (options) {
        L.Util.setOptions(this, options)
    },

    addTo: function (container) {
        container.addButton(this)
        return this
    },

    onAdd: function (buttonContainer) {
        this._buttonContainer = buttonContainer
        this._button = L.DomUtil.create("a", this.options.className, this._buttonContainer.getContainer())
        this._button.href = "#"
        this.setText(this.options.text)

        this._onClick = (event) => {
            this.options.onClick.call(this, event)
        }

        L.DomEvent.on(this._button, "click", L.DomEvent.stopPropagation)
            .on(this._button, "mousedown", L.DomEvent.stopPropagation)
            .on(this._button, "dblclick", L.DomEvent.stopPropagation)
            .on(this._button, "click", L.DomEvent.preventDefault)
            .on(this._button, "click", this._onClick, this)
    },

    remove: function () {
        L.DomEvent.off(this._button, "click", this._onClick)
        this._buttonContainer.getContainer().removeChild(this._button)
    },

    setText: function (text) {
        this._button.title = text
        this._button.innerHTML = text
    },
})

L.Control.ButtonContainer = L.Control.extend({
    options: {
        position: "topleft",
    },

    getContainer: function () {
        if (!this._container) {
            this._container = L.DomUtil.create("div", this.options.className)
        }
        return this._container
    },

    onAdd: function (map) {
        this._map = map
        return this.getContainer()
    },

    addButton: function (button) {
        button.onAdd(this)
    },

    addClass: function (className) {
        L.DomUtil.addClass(this.getContainer(), className)
    },

    removeClass: function (className) {
        L.DomUtil.removeClass(this.getContainer(), className)
    },
})

const LocationFilter = L.Class.extend({
    includes: L.Mixin.Events,

    options: {
        enableButton: {
            enableText: "Select area",
            disableText: "Remove selection",
        },
        adjustButton: {
            text: "Select area within current zoom",
        },
        buttonPosition: "topleft",
    },

    initialize: function (options) {
        L.Util.setOptions(this, options)
    },

    addTo: function (map) {
        map.addLayer(this)
        return this
    },

    onAdd: function (map) {
        this._map = map

        if (this.options.enableButton || this.options.adjustButton) {
            this._initializeButtonContainer()
        }

        if (this.options.enable) {
            this.enable()
        }
    },

    onRemove: function (map) {
        this.disable()
        if (this._buttonContainer) {
            this._buttonContainer.removeFrom(map)
        }
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
            clickable: false,
        }
        const mergedOptions = L.Util.extend(defaultOptions, options ?? {})
        const rect = new L.Rectangle(bounds, mergedOptions)
        rect.addTo(this._layer)
        return rect
    },

    /* Draw a draggable marker */
    _drawImageMarker: function (point, options) {
        const marker = new L.Marker(point, {
            icon: new L.DivIcon({
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
            className: "location-filter move-marker",
            anchor: [-10, -10],
            size: [13, 13],
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
            className: "location-filter resize-marker",
            anchor: [7, 6],
            size: [13, 12],
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
            ]
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
        const outerBounds = new L.LatLngBounds(
            new L.LatLng(mapBounds.getSouthWest().lat - 0.1, mapBounds.getSouthWest().lng - 0.1, true),
            new L.LatLng(mapBounds.getNorthEast().lat + 0.1, mapBounds.getNorthEast().lng + 0.1, true),
        )

        // The south west and north east points of the mask */
        this._osw = outerBounds.getSouthWest()
        this._one = outerBounds.getNorthEast()

        // Bounds for the mask rectangles
        this._northBounds = new L.LatLngBounds(new L.LatLng(this._ne.lat, this._osw.lng, true), this._one)
        this._westBounds = new L.LatLngBounds(new L.LatLng(this._sw.lat, this._osw.lng, true), this._nw)
        this._eastBounds = new L.LatLngBounds(this._se, new L.LatLng(this._ne.lat, this._one.lng, true))
        this._southBounds = new L.LatLngBounds(this._osw, new L.LatLng(this._sw.lat, this._one.lng, true))
    },

    /* Initializes rectangles and markers */
    _initialDraw: function () {
        if (this._initialDrawCalled) {
            return
        }

        this._layer = new L.LayerGroup()

        // Calculate filter bounds
        this._calculateBounds()

        // Create rectangles
        this._northRect = this._drawRectangle(this._northBounds)
        this._westRect = this._drawRectangle(this._westBounds)
        this._eastRect = this._drawRectangle(this._eastBounds)
        this._southRect = this._drawRectangle(this._southBounds)
        this._innerRect = this._drawRectangle(this.getBounds(), {
            fillOpacity: 0,
            stroke: true,
            color: "white",
            weight: 1,
            opacity: 0.9,
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
        const mergedOptions = L.Util.extend({ repositionResizeMarkers: true }, options)

        // Calculate filter bounds
        this._calculateBounds()

        // Reposition rectangles
        this._northRect.setBounds(this._northBounds)
        this._westRect.setBounds(this._westBounds)
        this._eastRect.setBounds(this._eastBounds)
        this._southRect.setBounds(this._southBounds)
        this._innerRect.setBounds(this.getBounds())

        // Reposition resize markers
        if (mergedOptions.repositionResizeMarkers) {
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
        let bounds
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

        // Update buttons
        if (this._buttonContainer) {
            this._buttonContainer.addClass("enabled")
        }

        if (this._enableButton) {
            this._enableButton.setText(this.options.enableButton.disableText)
        }

        if (this.options.adjustButton) {
            this._createAdjustButton()
        }

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

        // Update buttons
        if (this._buttonContainer) {
            this._buttonContainer.removeClass("enabled")
        }

        if (this._enableButton) {
            this._enableButton.setText(this.options.enableButton.enableText)
        }

        if (this._adjustButton) {
            this._adjustButton.remove()
        }

        // Remove event listener
        this._map.off("move", this._moveHandler)

        // Remove rectangle layer from map
        this._map.removeLayer(this._layer)

        this._enabled = false

        // Fire the disabled event
        this.fire("disabled")
    },

    /* Create a button that allows the user to adjust the location
       filter to the current zoom */
    _createAdjustButton: function () {
        this._adjustButton = new L.Control.Button({
            className: "adjust-button",
            text: this.options.adjustButton.text,

            onClick: () => {
                this._adjustToMap()
                this.fire("adjustToZoomClick")
            },
        }).addTo(this._buttonContainer)
    },

    /* Create the location filter button container and the button that
       toggles the location filter */
    _initializeButtonContainer: function () {
        this._buttonContainer = new L.Control.ButtonContainer({
            className: "location-filter button-container",
            position: this.options.buttonPosition,
        })

        if (this.options.enableButton) {
            this._enableButton = new L.Control.Button({
                className: "enable-button",
                text: this.options.enableButton.enableText,

                onClick: () => {
                    if (!this._enabled) {
                        // Enable the location filter
                        this.enable()
                        this.fire("enableClick")
                    } else {
                        // Disable the location filter
                        this.disable()
                        this.fire("disableClick")
                    }
                },
            }).addTo(this._buttonContainer)
        }

        this._buttonContainer.addTo(this._map)
    },
})

export const getLocationFilter = (options) => new LocationFilter(options)
