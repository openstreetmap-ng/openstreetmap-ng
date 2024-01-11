//= require qs/dist/qs

L.extend(L.LatLngBounds.prototype, {
    getSize: function () {
        return (this._northEast.lat - this._southWest.lat) * (this._northEast.lng - this._southWest.lng)
    },

    wrap: function () {
        return new L.LatLngBounds(this._southWest.wrap(), this._northEast.wrap())
    },
})

L.OSM.Map = L.Map.extend({
    initialize: function (id, options) {
        L.Map.prototype.initialize.call(this, id, options)

        this.baseLayers = []

        this.noteLayer = new L.FeatureGroup()
        this.noteLayer.options = { code: "N" }

        this.dataLayer = new L.OSM.DataLayer(null)
        this.dataLayer.options.code = "D"

        this.gpsLayer = new L.OSM.GPS({
            pane: "overlayPane",
            code: "G",
            name: I18n.t("javascripts.map.base.gps"),
        })

        this.on("layeradd", function (event) {
            if (this.baseLayers.indexOf(event.layer) >= 0) {
                this.setMaxZoom(event.layer.options.maxZoom)
            }
        })
    },

    updateLayers: function (layerParam) {
        var layers = layerParam || "M",
            layersAdded = ""

        for (var i = this.baseLayers.length - 1; i >= 0; i--) {
            if (layers.indexOf(this.baseLayers[i].options.code) >= 0) {
                this.addLayer(this.baseLayers[i])
                layersAdded = layersAdded + this.baseLayers[i].options.code
            } else if (i === 0 && layersAdded === "") {
                this.addLayer(this.baseLayers[i])
            } else {
                this.removeLayer(this.baseLayers[i])
            }
        }
    },

    getLayersCode: function () {
        // TODO: skip M
        var layerConfig = ""
        this.eachLayer(function (layer) {
            if (layer.options && layer.options.code) {
                layerConfig += layer.options.code
            }
        })
        return layerConfig
    },

    getMapBaseLayerId: function () {
        var baseLayerId
        this.eachLayer(function (layer) {
            if (layer.options && layer.options.keyid) baseLayerId = layer.options.keyid
        })
        return baseLayerId
    },

    addObject: function (object, callback) {
        this.removeObject()

        if (object.type === "note") {
            this._objectLoader = {
                abort: function () {},
            }

            this._object = object
            this._objectLayer = L.featureGroup().addTo(this)

            L.circleMarker(object.latLng, haloStyle).addTo(this._objectLayer)

            if (object.icon) {
                L.marker(object.latLng, {
                    icon: object.icon,
                    opacity: 1,
                    interactive: true,
                }).addTo(this._objectLayer)
            }

            if (callback) callback(this._objectLayer.getBounds())
        } else {
            // element or changeset handled by L.OSM.DataLayer
            var map = this
            this._objectLoader = $.ajax({
                url: OSM.apiUrl(object),
                dataType: "xml",
                success: function (xml) {
                    map._object = object

                    map._objectLayer = new L.OSM.DataLayer(null, {
                        styles: {
                            node: objectStyle,
                            way: objectStyle,
                            area: objectStyle,
                            changeset: changesetStyle,
                        },
                    })

                    map._objectLayer.interestingNode = function (node, ways, relations) {
                        if (object.type === "node") {
                            return true
                        } else if (object.type === "relation") {
                            for (var i = 0; i < relations.length; i++) {
                                if (relations[i].members.indexOf(node) !== -1) return true
                            }
                        } else {
                            return false
                        }
                    }

                    map._objectLayer.addData(xml)
                    map._objectLayer.addTo(map)

                    if (callback) callback(map._objectLayer.getBounds())
                },
            })
        }
    },

    removeObject: function () {
        this._object = null
        if (this._objectLoader) this._objectLoader.abort()
        if (this._objectLayer) this.removeLayer(this._objectLayer)
    },

    getState: function () {
        return {
            center: this.getCenter().wrap(),
            zoom: this.getZoom(),
            layers: this.getLayersCode(),
        }
    },

    setState: function (state, options) {
        if (state.center) this.setView(state.center, state.zoom, options)
        if (state.layers) this.updateLayers(state.layers)
    },

    setSidebarOverlaid: function (overlaid) {
        var sidebarWidth = 350
        if (overlaid && !$("#content").hasClass("overlay-sidebar")) {
            $("#content").addClass("overlay-sidebar")
            this.invalidateSize({ pan: false })
            if ($("html").attr("dir") !== "rtl") {
                this.panBy([-sidebarWidth, 0], { animate: false })
            }
        } else if (!overlaid && $("#content").hasClass("overlay-sidebar")) {
            if ($("html").attr("dir") !== "rtl") {
                this.panBy([sidebarWidth, 0], { animate: false })
            }
            $("#content").removeClass("overlay-sidebar")
            this.invalidateSize({ pan: false })
        }
        return this
    },
})

L.Icon.Default.imagePath = "/images/"

L.Icon.Default.imageUrls = {
    "/images/marker-icon.png": OSM.MARKER_ICON,
    "/images/marker-icon-2x.png": OSM.MARKER_ICON_2X,
    "/images/marker-shadow.png": OSM.MARKER_SHADOW,
}

L.extend(L.Icon.Default.prototype, {
    _oldGetIconUrl: L.Icon.Default.prototype._getIconUrl,

    _getIconUrl: function (name) {
        var url = this._oldGetIconUrl(name)
        return L.Icon.Default.imageUrls[url]
    },
})
