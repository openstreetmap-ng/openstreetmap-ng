import { configureRouter, defineRoute } from "@index/router"
import "../../../app/views/navbar/navbar-left"
import i18next from "i18next"

await i18next.init({
  lng: "en",
  resources: {
    en: {
      translation: {
        javascripts: {
          edit_help:
            "Move the map and zoom in on a location you want to edit, then click here.",
          site: { edit_disabled_tooltip: "Zoom in to edit the map" },
        },
        layouts: { edit: "Edit", history: "History" },
      },
    },
  },
})

configureRouter([
  defineRoute({ id: "index", path: "/", Component: () => null }),
  defineRoute({ id: "history", path: "/history", Component: () => null }),
])
