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

      // Add each row
      route.steps.forEach(function (step) {
        var ll = step[0],
            direction = step[1],
            instruction = step[2],
            dist = step[3],
            lineseg = step[4];

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
      });
