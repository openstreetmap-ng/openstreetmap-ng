locationFilter = new L.LocationFilter({
    enableButton: false,
    adjustButton: false,
})

locationFilter.on("change", update).addTo(map)

map.on("move", movedMap)
map.on("moveend layeradd layerremove", update)

$ui.on("show", shown).on("hide", hidden)

function shown() {
    $("#mapnik_scale").val(getScale())
    update()
}

function toggleFilter() {
    if ($(this).is(":checked")) {
        locationFilter.setBounds(map.getBounds().pad(-0.2))
        locationFilter.enable()
    } else {
        locationFilter.disable()
    }
    update()
}

function update() {
    var bounds = map.getBounds()

    $("#image_filter").prop("checked", locationFilter.isEnabled())

    // Image

    if (locationFilter.isEnabled()) {
        bounds = locationFilter.getBounds()
    }

    var scale = $("#mapnik_scale").val(),
        size = L.bounds(
            L.CRS.EPSG3857.project(bounds.getSouthWest()),
            L.CRS.EPSG3857.project(bounds.getNorthEast()),
        ).getSize(),
        maxScale = Math.floor(Math.sqrt((size.x * size.y) / 0.3136))

    $("#mapnik_minlon").val(bounds.getWest())
    $("#mapnik_minlat").val(bounds.getSouth())
    $("#mapnik_maxlon").val(bounds.getEast())
    $("#mapnik_maxlat").val(bounds.getNorth())

    if (scale < maxScale) {
        scale = roundScale(maxScale)
        $("#mapnik_scale").val(scale)
    }

    $("#mapnik_image_width").text(Math.round(size.x / scale / 0.00028))
    $("#mapnik_image_height").text(Math.round(size.y / scale / 0.00028))

    if (map.getMapBaseLayerId() === "mapnik") {
        $("#export-image").show()
        $("#export-warning").hide()
    } else {
        $("#export-image").hide()
        $("#export-warning").show()
    }
}

function getScale() {
    var bounds = map.getBounds(),
        centerLat = bounds.getCenter().lat,
        halfWorldMeters = 6378137 * Math.PI * Math.cos((centerLat * Math.PI) / 180),
        meters = (halfWorldMeters * (bounds.getEast() - bounds.getWest())) / 180,
        pixelsPerMeter = map.getSize().x / meters,
        metersPerPixel = 1 / (92 * 39.3701)
    return Math.round(1 / (pixelsPerMeter * metersPerPixel))
}

function roundScale(scale) {
    var precision = 5 * Math.pow(10, Math.floor(Math.LOG10E * Math.log(scale)) - 2)
    return precision * Math.ceil(scale / precision)
}
