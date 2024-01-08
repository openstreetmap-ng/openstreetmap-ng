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

        var copyright_link = $("<a>", {
            href: "/copyright",
            text: I18n.t("javascripts.map.openstreetmap_contributors"),
        }).prop("outerHTML")
        var copyright = I18n.t("javascripts.map.copyright_text", { copyright_link: copyright_link })

        var donate = $("<a>", {
            href: "https://supporting.openstreetmap.org",
            class: "donate-attr",
            text: I18n.t("javascripts.map.make_a_donation"),
        }).prop("outerHTML")

        var terms = $("<a>", {
            href: "https://wiki.osmfoundation.org/wiki/Terms_of_Use",
            text: I18n.t("javascripts.map.website_and_api_terms"),
        }).prop("outerHTML")

        var cyclosm_link = $("<a>", {
            href: "https://www.cyclosm.org",
            target: "_blank",
            text: I18n.t("javascripts.map.cyclosm_name"),
        }).prop("outerHTML")
        var osm_france_link = $("<a>", {
            href: "https://openstreetmap.fr/",
            target: "_blank",
            text: I18n.t("javascripts.map.osm_france"),
        }).prop("outerHTML")
        var cyclosm = I18n.t("javascripts.map.cyclosm_credit", {
            cyclosm_link: cyclosm_link,
            osm_france_link: osm_france_link,
        })

        var thunderforest_link = $("<a>", {
            href: "https://www.thunderforest.com/",
            target: "_blank",
            text: I18n.t("javascripts.map.andy_allan"),
        }).prop("outerHTML")
        var thunderforest = I18n.t("javascripts.map.thunderforest_credit", { thunderforest_link: thunderforest_link })

        var memomaps_link = $("<a>", {
            href: "https://memomaps.de/",
            target: "_blank",
            text: I18n.t("javascripts.map.memomaps"),
        }).prop("outerHTML")
        var memomaps = I18n.t("javascripts.map.opnvkarte_credit", { memomaps_link: memomaps_link })

        var hotosm_link = $("<a>", {
            href: "https://www.hotosm.org/",
            target: "_blank",
            text: I18n.t("javascripts.map.hotosm_name"),
        }).prop("outerHTML")
        var hotosm = I18n.t("javascripts.map.hotosm_credit", {
            hotosm_link: hotosm_link,
            osm_france_link: osm_france_link,
        })

        this.baseLayers = []

        this.baseLayers.push(
            new L.OSM.Mapnik({
                attribution: copyright + " &hearts; " + donate + ". " + terms,
                code: "M",
                keyid: "mapnik",
                name: I18n.t("javascripts.map.base.standard"),
            }),
        )

        this.baseLayers.push(
            new L.OSM.CyclOSM({
                attribution: copyright + ". " + cyclosm + ". " + terms,
                code: "Y",
                keyid: "cyclosm",
                name: I18n.t("javascripts.map.base.cyclosm"),
            }),
        )

        if (OSM.THUNDERFOREST_KEY) {
            this.baseLayers.push(
                new L.OSM.CycleMap({
                    attribution: copyright + ". " + thunderforest + ". " + terms,
                    apikey: OSM.THUNDERFOREST_KEY,
                    code: "C",
                    keyid: "cyclemap",
                    name: I18n.t("javascripts.map.base.cycle_map"),
                }),
            )

            this.baseLayers.push(
                new L.OSM.TransportMap({
                    attribution: copyright + ". " + thunderforest + ". " + terms,
                    apikey: OSM.THUNDERFOREST_KEY,
                    code: "T",
                    keyid: "transportmap",
                    name: I18n.t("javascripts.map.base.transport_map"),
                }),
            )
        }

        this.baseLayers.push(
            new L.OSM.OPNVKarte({
                attribution: copyright + ". " + memomaps + ". " + terms,
                code: "O",
                keyid: "opnvkarte",
                name: I18n.t("javascripts.map.base.opnvkarte"),
            }),
        )

        this.baseLayers.push(
            new L.OSM.HOT({
                attribution: copyright + ". " + hotosm + ". " + terms,
                code: "H",
                keyid: "hot",
                name: I18n.t("javascripts.map.base.hot"),
            }),
        )

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
        var objectStyle = {
            color: "#FF6200",
            weight: 4,
            opacity: 1,
            fillOpacity: 0.5,
        }

        var changesetStyle = {
            weight: 4,
            color: "#FF9500",
            opacity: 1,
            fillOpacity: 0,
            interactive: false,
        }

        var haloStyle = {
            weight: 2.5,
            radius: 20,
            fillOpacity: 0.5,
            color: "#FF6200",
        }

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
