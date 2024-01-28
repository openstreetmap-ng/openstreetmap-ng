
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
