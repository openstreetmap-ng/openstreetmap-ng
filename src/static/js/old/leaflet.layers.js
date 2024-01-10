var addOverlay = function (layer, name, maxArea) {
  input.on("change", function () {
    checked = input.is(":checked");
    if (checked) {
      map.addLayer(layer);
    } else {
      map.removeLayer(layer);
    }
    map.fire("overlaylayerchange", { layer: layer });
  });

  map.on("layeradd layerremove", function () {
    input.prop("checked", map.hasLayer(layer));
  });

  map.on("zoomend", function () {
    var disabled = map.getBounds().getSize() >= maxArea;
    $(input).prop("disabled", disabled);

    if (disabled && $(input).is(":checked")) {
      $(input).prop("checked", false)
        .trigger("change");
      checked = true;
    } else if (!disabled && !$(input).is(":checked") && checked) {
      $(input).prop("checked", true)
        .trigger("change");
    }

    $(item)
      .attr("class", disabled ? "disabled" : "")
      .tooltip(disabled ? "enable" : "disable");
  });
};
