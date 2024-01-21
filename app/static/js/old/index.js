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

OSM.initializeNotes(map)
OSM.initializeBrowse(map)

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
