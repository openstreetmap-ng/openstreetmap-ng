L.OSM.Map = L.Map.extend({
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
