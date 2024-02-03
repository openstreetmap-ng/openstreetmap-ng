      $.getJSON(OSM.NOMINATIM_URL + "search?q=" + encodeURIComponent(endpoint.value) + "&format=json&viewbox=" + viewbox, function (json) {
        endpoint.awaitingGeocode = false;
        endpoint.hasGeocode = true;
        if (json.length === 0) {
          input.addClass("error");
          alert(I18n.t("javascripts.directions.errors.no_place", { place: endpoint.value }));
          return;
        }

        endpoint.setLatLng(L.latLng(json[0]));

        input.val(json[0].display_name);

        if (awaitingGeocode) {
          awaitingGeocode = false;
          getRoute(true, true);
        }
      });

  function getRoute(fitRoute, reportErrors) {
    // Cancel any route that is already in progress
    if (awaitingRoute) awaitingRoute.abort();

    // go fetch geocodes for any endpoints which have not already
    // been geocoded.
    for (var ep_i = 0; ep_i < 2; ++ep_i) {
      var endpoint = endpoints[ep_i];
      if (!endpoint.hasGeocode && !endpoint.awaitingGeocode) {
        endpoint.getGeocode();
        awaitingGeocode = true;
      }
    }
    if (endpoints[0].awaitingGeocode || endpoints[1].awaitingGeocode) {
      awaitingGeocode = true;
      return;
    }

    var o = endpoints[0].latlng,
        d = endpoints[1].latlng;

    if (!o || !d) return;
    $("header").addClass("closed");

    var precision = OSM.zoomPrecision(map.getZoom());

    OSM.router.replace("/directions?" + Qs.stringify({
      engine: chosenEngine.id,
      route: o.lat.toFixed(precision) + "," + o.lng.toFixed(precision) + ";" +
             d.lat.toFixed(precision) + "," + d.lng.toFixed(precision)
    }));

    // copy loading item to sidebar and display it. we copy it, rather than
    // just using it in-place and replacing it in case it has to be used
    // again.
    $("#sidebar_content").html($(".directions_form .loader_copy").html());
    map.setSidebarOverlaid(false);

    awaitingRoute = chosenEngine.getRoute([o, d], function (err, route) {
      awaitingRoute = null;

      if (err) {
        map.removeLayer(polyline);

        if (reportErrors) {
          $("#sidebar_content").html("<p class=\"search_results_error\">" + I18n.t("javascripts.directions.errors.no_route") + "</p>");
        }

        return;
      }

      polyline
        .setLatLngs(route.line)
        .addTo(map);

      if (fitRoute) {
        map.fitBounds(polyline.getBounds().pad(0.05));
      }

      var distanceText = $("<p>").append(
        I18n.t("javascripts.directions.distance") + ": " + formatDistance(route.distance) + ". " +
        I18n.t("javascripts.directions.time") + ": " + formatTime(route.time) + ".");
      if (typeof route.ascend !== "undefined" && typeof route.descend !== "undefined") {
        distanceText.append(
          $("<br>"),
          I18n.t("javascripts.directions.ascend") + ": " + formatHeight(route.ascend) + ". " +
          I18n.t("javascripts.directions.descend") + ": " + formatHeight(route.descend) + ".");
      }

      var turnByTurnTable = $("<table class='table table-sm mb-3'>")
        .append($("<tbody>"));
      var directionsCloseButton = $("<button type='button' class='btn-close'>")
        .attr("aria-label", I18n.t("javascripts.close"));

      $("#sidebar_content")
        .empty()
        .append(
          $("<div class='d-flex'>").append(
            $("<h2 class='flex-grow-1 text-break'>")
              .text(I18n.t("javascripts.directions.directions")),
            $("<div>").append(directionsCloseButton)),
          distanceText,
          turnByTurnTable
        );

      // Add each row
      route.steps.forEach(function (step) {
        var ll = step[0],
            direction = step[1],
            instruction = step[2],
            dist = step[3],
            lineseg = step[4];

        if (dist < 5) {
          dist = "";
        } else if (dist < 200) {
          dist = String(Math.round(dist / 10) * 10) + "m";
        } else if (dist < 1500) {
          dist = String(Math.round(dist / 100) * 100) + "m";
        } else if (dist < 5000) {
          dist = String(Math.round(dist / 100) / 10) + "km";
        } else {
          dist = String(Math.round(dist / 1000)) + "km";
        }

        var row = $("<tr class='turn'/>");
        row.append("<td class='border-0'><div class='direction i" + direction + "'/></td> ");
        row.append("<td>" + instruction);
        row.append("<td class='distance'>" + dist);

        row.on("click", function () {
          popup
            .setLatLng(ll)
            .setContent("<p>" + instruction + "</p>")
            .openOn(map);
        });

        row.hover(function () {
          highlight
            .setLatLngs(lineseg)
            .addTo(map);
        }, function () {
          map.removeLayer(highlight);
        });

        turnByTurnTable.append(row);
      });

      $("#sidebar_content").append("<p class=\"text-center\">" +
        I18n.t("javascripts.directions.instructions.courtesy", { link: chosenEngine.creditline }) +
        "</p>");

      directionsCloseButton.on("click", function () {
        map.removeLayer(polyline);
        $("#sidebar_content").html("");
        map.setSidebarOverlaid(true);
        // TODO: collapse width of sidebar back to previous
      });
    });
  }

  var chosenEngineIndex = findEngine("fossgis_osrm_car");
  if (Cookies.get("_osm_directions_engine")) {
    chosenEngineIndex = findEngine(Cookies.get("_osm_directions_engine"));
  }
  setEngine(chosenEngineIndex);

  select.on("change", function (e) {
    chosenEngine = engines[e.target.selectedIndex];
    Cookies.set("_osm_directions_engine", chosenEngine.id, { secure: true, expires: expiry, path: "/", samesite: "lax" });
    getRoute(true, true);
  });

  $(".directions_form").on("submit", function (e) {
    e.preventDefault();
    getRoute(true, true);
  });

  $(".routing_marker").on("dragstart", function (e) {
    var dt = e.originalEvent.dataTransfer;
    dt.effectAllowed = "move";
    var dragData = { type: $(this).data("type") };
    dt.setData("text", JSON.stringify(dragData));
    if (dt.setDragImage) {
      var img = $("<img>").attr("src", $(e.originalEvent.target).attr("src"));
      dt.setDragImage(img.get(0), 12, 21);
    }
  });

  var page = {};

  page.pushstate = page.popstate = function () {
    $(".search_form").hide();
    $(".directions_form").show();

    $("#map").on("dragend dragover", function (e) {
      e.preventDefault();
    });

    $("#map").on("drop", function (e) {
      e.preventDefault();
      var oe = e.originalEvent;
      var dragData = JSON.parse(oe.dataTransfer.getData("text"));
      var type = dragData.type;
      var pt = L.DomEvent.getMousePosition(oe, map.getContainer()); // co-ordinates of the mouse pointer at present
      pt.y += 20;
      var ll = map.containerPointToLatLng(pt);
      endpoints[type === "from" ? 0 : 1].setLatLng(ll);
      getRoute(true, true);
    });

    var params = Qs.parse(location.search.substring(1)),
        route = (params.route || "").split(";"),
        from = route[0] && L.latLng(route[0].split(",")),
        to = route[1] && L.latLng(route[1].split(","));

    if (params.engine) {
      var engineIndex = findEngine(params.engine);

      if (engineIndex >= 0) {
        setEngine(engineIndex);
      }
    }

    endpoints[0].setValue(params.from || "", from);
    endpoints[1].setValue(params.to || "", to);

    map.setSidebarOverlaid(!from || !to);

    getRoute(true, true);
  };

  page.load = function () {
    page.pushstate();
  };

  page.unload = function () {
    $(".search_form").show();
    $(".directions_form").hide();
    $("#map").off("dragend dragover drop");

    map
      .removeLayer(popup)
      .removeLayer(polyline)
      .removeLayer(endpoints[0].marker)
      .removeLayer(endpoints[1].marker);
  };

  return page;
};
