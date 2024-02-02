$(".search_form input[name=query]").on("input", function (e) {
    if ($(e.target).val() === "") {
        $(".describe_location").fadeIn(100)
    } else {
        $(".describe_location").fadeOut(100)
    }
})

$(".search_form a.button.switch_link").on("click", function (e) {
    e.preventDefault()
    var query = $(e.target).parent().parent().find("input[name=query]").val()
    if (query) {
        OSM.router.route("/directions?from=" + encodeURIComponent(query) + OSM.formatHash(map))
    } else {
        OSM.router.route("/directions" + OSM.formatHash(map))
    }
})

$(".search_form").on("submit", function (e) {
    e.preventDefault()
    $("header").addClass("closed")
    var query = $(this).find("input[name=query]").val()
    if (query) {
        OSM.router.route("/search?query=" + encodeURIComponent(query) + OSM.formatHash(map))
    } else {
        OSM.router.route("/" + OSM.formatHash(map))
    }
})

$(".describe_location").on("click", function (e) {
    e.preventDefault()
    var center = map.getCenter().wrap(),
        precision = OSM.zoomPrecision(map.getZoom())
    OSM.router.route(
        "/search?whereami=1&query=" +
            encodeURIComponent(center.lat.toFixed(precision) + "," + center.lng.toFixed(precision)),
    )
})
