
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
