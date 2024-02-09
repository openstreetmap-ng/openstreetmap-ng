import { Tooltip } from "bootstrap"
import i18next from "i18next"
import * as L from "leaflet"
import "leaflet.locatecontrol"
import { isMetricUnit } from "../_utils.js"

// TODO: onlocationerror

export const getGeolocateControl = () => {
    const control = L.control.locate({
        position: "topright",
        icon: "icon geolocate",
        iconLoading: "icon geolocate",
        metric: isMetricUnit,
        strings: {
            title: i18next.t("javascripts.map.locate.title"),
            popup: ({ distance, unit }) => {
                const count = Math.round(distance)
                // hard-coded strings for searchability
                if (unit === "meters") return i18next.t("javascripts.map.locate.metersPopup", { count })
                if (unit === "feet") return i18next.t("javascripts.map.locate.feetPopup", { count })
                console.error(`Unknown unit: ${unit}`)
            },
        },
        createButtonCallback: (container, options) => {
            container.className = "leaflet-control geolocate"

            // Create button and tooltip
            const locateButton = document.createElement("button")
            locateButton.className = "control-button"
            locateButton.innerHTML = `<span class="${options.icon}"></span>`

            const locateTooltip = new Tooltip(locateButton, {
                title: i18next.t("javascripts.map.locate.title"),
                placement: "left",
            })

            // Add button to container
            container.appendChild(locateButton)

            return { link: locateButton, icon: locateButton.querySelector("span") }
        },
        /*
        createButtonCallback(container, options) {
        const link = L.DomUtil.create("a", "leaflet-bar-part leaflet-bar-part-single", container);
        link.title = options.strings.title;
        link.href = "#";
        link.setAttribute("role", "button");
        const icon = L.DomUtil.create(options.iconElementTag, options.icon, link);

        if (options.strings.text !== undefined) {
          const text = L.DomUtil.create(options.textElementTag, "leaflet-locate-text", link);
          text.textContent = options.strings.text;
          link.classList.add("leaflet-locate-text-active");
          link.parentNode.style.display = "flex";
          if (options.icon.length > 0) {
            icon.classList.add("leaflet-locate-icon");
          }
        }

        return { link, icon };
      }*/
    })

    return control
}
