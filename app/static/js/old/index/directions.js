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
