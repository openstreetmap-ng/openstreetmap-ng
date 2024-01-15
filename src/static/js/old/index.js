$(document).ready(function () {
    OSM.loadSidebarContent = function (path, callback) {
        loaderTimeout = setTimeout(function () {
            $("#sidebar_loader").show()
        }, 200)

        $.ajax({
            url: content_path,
            dataType: "html",
            complete: function (xhr) {
                clearTimeout(loaderTimeout)
                $("#flash").empty()
                $("#sidebar_loader").hide()

                var content = $(xhr.responseText)

                if (xhr.getResponseHeader("X-Page-Title")) {
                    var title = xhr.getResponseHeader("X-Page-Title")
                    document.title = decodeURIComponent(title)
                }

                $("head").find('link[type="application/atom+xml"]').remove()

                $("head").append(content.filter('link[type="application/atom+xml"]'))

                $("#sidebar_content").html(content.not('link[type="application/atom+xml"]'))

                if (callback) {
                    callback()
                }
            },
        })
    }

    OSM.initializeContextMenu(map)

    if (OSM.STATUS !== "api_offline" && OSM.STATUS !== "database_offline") {
        OSM.initializeNotes(map)
        OSM.initializeBrowse(map)
    }

    if (Cookies.get("_osm_welcome") !== "hide") {
        $(".welcome").removeAttr("hidden")
    }

    $(".welcome .btn-close").on("click", function () {
        $(".welcome").hide()
        Cookies.set("_osm_welcome", "hide", { secure: true, expires: expiry, path: "/", samesite: "lax" })
    })

    var bannerExpiry = new Date()
    bannerExpiry.setYear(bannerExpiry.getFullYear() + 1)

    $("#banner .btn-close").on("click", function (e) {
        var cookieId = e.target.id
        $("#banner").hide()
        e.preventDefault()
        if (cookieId) {
            Cookies.set(cookieId, "hide", { secure: true, expires: bannerExpiry, path: "/", samesite: "lax" })
        }
    })

    if (OSM.MATOMO) {
        map.on("layeradd", function (e) {
            if (e.layer.options) {
                var goal = OSM.MATOMO.goals[e.layer.options.keyid]

                if (goal) {
                    $("body").trigger("matomogoal", goal)
                }
            }
        })
    }

    if (params.bounds) {
        map.fitBounds(params.bounds)
    } else {
        map.setView([params.lat, params.lon], params.zoom)
    }

    if (params.marker) {
        L.marker([params.mlat, params.mlon]).addTo(map)
    }

    $("#homeanchor").on("click", function (e) {
        e.preventDefault()

        var data = $(this).data(),
            center = L.latLng(data.lat, data.lon)

        map.setView(center, data.zoom)
        L.marker(center, { icon: OSM.getUserIcon() }).addTo(map)
    })

    function remoteEditHandler(bbox, object) {
        var remoteEditHost = "http://127.0.0.1:8111",
            osmHost = location.protocol + "//" + location.host,
            query = {
                left: bbox.getWest() - 0.0001,
                top: bbox.getNorth() + 0.0001,
                right: bbox.getEast() + 0.0001,
                bottom: bbox.getSouth() - 0.0001,
            }

        if (object && object.type !== "note") query.select = object.type + object.id // can't select notes
        sendRemoteEditCommand(remoteEditHost + "/load_and_zoom?" + Qs.stringify(query), function () {
            if (object && object.type === "note") {
                var noteQuery = { url: osmHost + OSM.apiUrl(object) }
                sendRemoteEditCommand(remoteEditHost + "/import?" + Qs.stringify(noteQuery))
            }
        })

        function sendRemoteEditCommand(url, callback) {
            var iframe = $("<iframe>")
            var timeoutId = setTimeout(function () {
                alert(I18n.t("site.index.remote_failed"))
                iframe.remove()
            }, 5000)

            iframe
                .hide()
                .appendTo("body")
                .attr("src", url)
                .on("load", function () {
                    clearTimeout(timeoutId)
                    iframe.remove()
                    if (callback) callback()
                })
        }

        return false
    }

    $("a[data-editor=remote]").click(function (e) {
        var params = OSM.mapParams(this.search)
        remoteEditHandler(map.getBounds(), params.object)
        e.preventDefault()
    })

    if (OSM.params().edit_help) {
        $("#editanchor")
            .removeAttr("title")
            .tooltip({
                placement: "bottom",
                title: I18n.t("javascripts.edit_help"),
            })
            .tooltip("show")

        $("body").one("click", function () {
            $("#editanchor").tooltip("hide")
        })
    }

    OSM.Index = function (map) {
        var page = {}

        page.pushstate = page.popstate = function () {
            map.setSidebarOverlaid(true)
            document.title = I18n.t("layouts.project_name.title")
        }

        page.load = function () {
            var params = Qs.parse(location.search.substring(1))
            if (params.query) {
                $("#sidebar .search_form input[name=query]").value(params.query)
            }
            if (!("autofocus" in document.createElement("input"))) {
                $("#sidebar .search_form input[name=query]").focus()
            }
            return map.getState()
        }

        return page
    }

    OSM.Browse = function (map, type) {
        var page = {}

        page.pushstate = page.popstate = function (path, id) {
            OSM.loadSidebarContent(path, function () {
                addObject(type, id)
            })
        }

        page.load = function (path, id) {
            addObject(type, id, true)
        }

        function addObject(type, id, center) {
            map.addObject({ type: type, id: parseInt(id, 10) }, function (bounds) {
                if (!window.location.hash && bounds.isValid() && (center || !map.getBounds().contains(bounds))) {
                    OSM.router.withoutMoveListener(function () {
                        map.fitBounds(bounds)
                    })
                }
            })

            $(".colour-preview-box").each(function () {
                $(this).css("background-color", $(this).data("colour"))
            })
        }

        page.unload = function () {
            map.removeObject()
        }

        return page
    }

    var history = OSM.History(map)

    OSM.router = OSM.Router(map, {
        "/": OSM.Index(map),
        "/search": OSM.Search(map),
        "/directions": OSM.Directions(map),
        "/export": OSM.Export(map),
        "/note/new": OSM.NewNote(map),
        "/history/friends": history,
        "/history/nearby": history,
        "/history": history,
        "/user/:display_name/history": history,
        "/note/:id": OSM.Note(map),
        "/node/:id(/history)": OSM.Browse(map, "node"),
        "/way/:id(/history)": OSM.Browse(map, "way"),
        "/relation/:id(/history)": OSM.Browse(map, "relation"),
        "/changeset/:id": OSM.Changeset(map),
        "/query": OSM.Query(map),
    })

    if (OSM.preferred_editor === "remote" && document.location.pathname === "/edit") {
        remoteEditHandler(map.getBounds(), params.object)
        OSM.router.setCurrentPath("/")
    }

    OSM.router.load()

    $(document).on("click", "a", function (e) {
        if (e.isDefaultPrevented() || e.isPropagationStopped()) {
            return
        }

        // Open links in a new tab as normal.
        if (e.which > 1 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) {
            return
        }

        // Ignore cross-protocol and cross-origin links.
        if (location.protocol !== this.protocol || location.host !== this.host) {
            return
        }

        if (OSM.router.route(this.pathname + this.search + this.hash)) {
            e.preventDefault()
        }
    })

    $(document).on("click", "#sidebar_content .btn-close", function () {
        OSM.router.route("/" + OSM.formatHash(map))
    })
})
