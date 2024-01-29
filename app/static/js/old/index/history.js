function update() {
  var data = { list: "1" };

  if (window.location.pathname === "/history") {
    data.bbox = map.getBounds().wrap().toBBoxString();
    var feedLink = $("link[type=\"application/atom+xml\"]"),
        feedHref = feedLink.attr("href").split("?")[0];
    feedLink.attr("href", feedHref + "?bbox=" + data.bbox);
  }

  $.ajax({
    url: window.location.pathname,
    method: "GET",
    data: data,
    success: function (html) {
      displayFirstChangesets(html);
      updateMap();
    }
  });
}

function loadMore(e) {
  e.preventDefault();
  e.stopPropagation();

  var div = $(this).parents(".changeset_more");

  $(this).hide();
  div.find(".loader").show();

  $.get($(this).attr("href"), function (html) {
    displayMoreChangesets(html);
    updateMap();
  });
}
