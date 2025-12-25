import { routerNavigateStrict } from "@index/router"
import { beautifyZoom, zoomPrecision } from "@lib/coords"
import { qsEncode } from "@lib/qs"
import { signal } from "@preact/signals"
import { t } from "i18next"
import type { Map as MaplibreMap } from "maplibre-gl"
import { render } from "preact"

export const searchFormQuery = signal("")

const SearchForm = ({ map }: { map: MaplibreMap }) => {
  const onSubmit = (e: Event) => {
    console.debug("SearchForm: Submitted")
    e.preventDefault()
    const query = searchFormQuery.value
    if (query) routerNavigateStrict(`/search${qsEncode({ q: query })}`)
  }

  const onWhereIsThisClick = () => {
    console.debug("SearchForm: Where is this clicked")
    const zoom = map.getZoom()
    const precision = zoomPrecision(zoom)
    const lngLat = map.getCenter()
    routerNavigateStrict(
      `/search${qsEncode({
        lat: lngLat.lat.toFixed(precision),
        lon: lngLat.lng.toFixed(precision),
        zoom: beautifyZoom(zoom),
      })}`,
    )
  }

  return (
    <form
      class="search-form"
      onSubmit={onSubmit}
    >
      <div class="row g-2">
        <div class="col">
          <div class="input-group">
            <input
              type="text"
              class="form-control"
              placeholder={t("site.search.search")}
              enterKeyHint="search"
              required
              value={searchFormQuery.value}
              onInput={(e) => (searchFormQuery.value = e.currentTarget.value)}
            />
            <button
              class="btn btn-link where-is-this"
              type="button"
              title={t("site.search.where_am_i_title")}
              onClick={onWhereIsThisClick}
            >
              {t("site.search.where_am_i")}
            </button>
            <button
              class="btn btn-primary"
              type="submit"
              title={t("action.submit")}
            >
              <svg
                width="22"
                height="20"
                aria-hidden="true"
              >
                <circle
                  cx="13"
                  cy="7"
                  r="6.5"
                  fill="#fff8"
                  stroke="#fff"
                />
                <path
                  d="M9.75 12.629 A6.5 6.5 0 0 1 7.371 10.25"
                  fill="none"
                  stroke="#fff"
                  stroke-width="1.5"
                />
                <line
                  x1="1"
                  y1="19"
                  x2="6.5"
                  y2="13.5"
                  stroke="#fff8"
                  stroke-width="2"
                />
                <line
                  x1="1.5"
                  y1="18.5"
                  x2="6"
                  y2="14"
                  stroke="#fff"
                  stroke-width="2.5"
                />
                <line
                  x1="6.5"
                  y1="13.5"
                  x2="8.5"
                  y2="11.5"
                  stroke="#fff"
                  stroke-width="1.5"
                />
              </svg>
            </button>
          </div>
        </div>

        <div class="col-auto">
          <a
            class="btn btn-primary"
            href="/directions"
            title={t("site.search.get_directions_title")}
          >
            <svg
              width="28"
              height="20"
              aria-hidden="true"
            >
              <path
                d="M11.5 9.5 v-3h3v-1l-5 -5l-5 5v1h3v6"
                fill="none"
                stroke="#fff8"
              />
              <path
                d="M7.5 19.5h4v-5a1 1 0 0 1 1 -1h5v3h1l5 -5l-5 -5h-1v3h-6a4 4 0 0 0 -4 4z"
                fill="#fff8"
                stroke="#fff"
              />
            </svg>
          </a>
        </div>
      </div>
    </form>
  )
}

/** Configure the search form */
export const configureSearchForm = (map: MaplibreMap) => {
  const container = document.getElementById("SearchForm")!
  render(<SearchForm map={map} />, container)
}
