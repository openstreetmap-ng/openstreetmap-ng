function featurePrefix(feature) {
  var tags = feature.tags;
  var prefix = "";

  if (tags.boundary === "administrative" && tags.admin_level) {
    prefix = I18n.t("geocoder.search_osm_nominatim.admin_levels.level" + tags.admin_level, {
      defaultValue: I18n.t("geocoder.search_osm_nominatim.prefix.boundary.administrative")
    });
  } else {
    var prefixes = I18n.t("geocoder.search_osm_nominatim.prefix");
    var key, value;

    for (key in tags) {
      value = tags[key];

      if (prefixes[key]) {
        if (prefixes[key][value]) {
          return prefixes[key][value];
        }
      }
    }

    for (key in tags) {
      value = tags[key];

      if (prefixes[key]) {
        var first = value.slice(0, 1).toUpperCase(),
            rest = value.slice(1).replace(/_/g, " ");

        return first + rest;
      }
    }
  }

  if (!prefix) {
    prefix = I18n.t("javascripts.query." + feature.type);
  }

  return prefix;
}

function featureName(feature) {
  var tags = feature.tags,
      locales = I18n.locales.get();

  for (var i = 0; i < locales.length; i++) {
    if (tags["name:" + locales[i]]) {
      return tags["name:" + locales[i]];
    }
  }

  if (tags.name) {
    return tags.name;
  } else if (tags.ref) {
    return tags.ref;
  } else if (tags["addr:housename"]) {
    return tags["addr:housename"];
  } else if (tags["addr:housenumber"] && tags["addr:street"]) {
    return tags["addr:housenumber"] + " " + tags["addr:street"];
  } else {
    return "#" + feature.id;
  }
}

function runQuery(latlng, radius, query, $section, merge, compare) {
  $section.data("ajax", $.ajax({
    url: url,
    method: "POST",
    data: {
      data: "[timeout:10][out:json];" + query
    },
    xhrFields: {
      withCredentials: credentials
    },
    success: function (results) {
      var elements;

      $section.find(".loader").hide();

      if (merge) {
        elements = results.elements.reduce(function (hash, element) {
          var key = element.type + element.id;
          if ("geometry" in element) {
            delete element.bounds;
          }
          hash[key] = $.extend({}, hash[key], element);
          return hash;
        }, {});

        elements = Object.keys(elements).map(function (key) {
          return elements[key];
        });
      } else {
        elements = results.elements;
      }

      if (compare) {
        elements = elements.sort(compare);
      }

      for (var i = 0; i < elements.length; i++) {
        var element = elements[i];

        if (interestingFeature(element)) {
          var $li = $("<li>")
            .addClass("query-result list-group-item")
            .data("geometry", featureGeometry(element))
            .text(featurePrefix(element) + " ")
            .appendTo($ul);

          $("<a>")
            .attr("href", "/" + element.type + "/" + element.id)
            .text(featureName(element))
            .appendTo($li);
        }
      }

      if (results.remark) {
        $("<li>")
          .addClass("query-result list-group-item")
          .text(I18n.t("javascripts.query.error", { server: url, error: results.remark }))
          .appendTo($ul);
      }

      if ($ul.find("li").length === 0) {
        $("<li>")
          .addClass("query-result list-group-item")
          .text(I18n.t("javascripts.query.nothing_found"))
          .appendTo($ul);
      }
    },
  }));
}

function compareSize(feature1, feature2) {
  var width1 = feature1.bounds.maxlon - feature1.bounds.minlon,
      height1 = feature1.bounds.maxlat - feature1.bounds.minlat,
      area1 = width1 * height1,
      width2 = feature2.bounds.maxlat - feature2.bounds.minlat,
      height2 = feature2.bounds.maxlat - feature2.bounds.minlat,
      area2 = width2 * height2;

  return area1 - area2;
}

/*
  * To find nearby objects we ask overpass for the union of the
  * following sets:
  *
  *   node(around:<radius>,<lat>,lng>)
  *   way(around:<radius>,<lat>,lng>)
  *   relation(around:<radius>,<lat>,lng>)
  *
  * to find enclosing objects we first find all the enclosing areas:
  *
  *   is_in(<lat>,<lng>)->.a
  *
  * and then return the union of the following sets:
  *
  *   relation(pivot.a)
  *   way(pivot.a)
  *
  * In both cases we then ask to retrieve tags and the geometry
  * for each object.
  */
function queryOverpass(lat, lng) {
  var latlng = L.latLng(lat, lng).wrap(),
      bounds = map.getBounds().wrap(),
      precision = OSM.zoomPrecision(map.getZoom()),
      bbox = bounds.getSouth().toFixed(precision) + "," +
              bounds.getWest().toFixed(precision) + "," +
              bounds.getNorth().toFixed(precision) + "," +
              bounds.getEast().toFixed(precision),
      radius = 10 * Math.pow(1.5, 19 - map.getZoom()),
      around = "around:" + radius + "," + lat + "," + lng,
      nodes = "node(" + around + ")",
      ways = "way(" + around + ")",
      relations = "relation(" + around + ")",
      nearby = "(" + nodes + ";" + ways + ";);out tags geom(" + bbox + ");" + relations + ";out geom(" + bbox + ");",
      isin = "is_in(" + lat + "," + lng + ")->.a;way(pivot.a);out tags bb;out ids geom(" + bbox + ");relation(pivot.a);out tags bb;";

  $("#sidebar_content .query-intro")
    .hide();

  runQuery(latlng, radius, nearby, $("#query-nearby"), false);
  runQuery(latlng, radius, isin, $("#query-isin"), true, compareSize);
}

function enableQueryMode() {
  queryButton.addClass("active");
  map.on("click", clickHandler);
  $(map.getContainer()).addClass("query-active");
}

function disableQueryMode() {
  if (marker) map.removeLayer(marker);
  $(map.getContainer()).removeClass("query-active").removeClass("query-disabled");
  map.off("click", clickHandler);
  queryButton.removeClass("active");
}
