import { useSignal } from "@preact/signals"
import { mountProtoPage } from "@lib/proto-page"
import { PageSchema } from "@lib/proto/software_pb"
import { t } from "i18next"

const ALL = "all"

type SoftwareEntry = {
  name: string
  shortName: string
  description: string
  href: string
  category: string
  platforms: string[]
  license: string
  status: string
  image: string
}

const categories = [
  "Editing",
  "Mobile mapping",
  "Map display",
  "Quality assurance",
  "Data services",
  "Developer tools",
]

const platforms = ["Web", "Windows", "macOS", "Linux", "Android", "iOS", "Server"]

const licenses = ["Open source", "Mixed", "Proprietary"]
const statuses = ["Active", "Mature", "Specialized"]

const softwareEntries: SoftwareEntry[] = [
  {
    name: "iD",
    shortName: "iD",
    description:
      "Browser editor for quick map edits, walkthroughs, imagery tracing, and tag cleanup.",
    href: "https://www.openstreetmap.org/edit?editor=id",
    category: "Editing",
    platforms: ["Web"],
    license: "Open source",
    status: "Active",
    image: "https://ideditor.net/img/iD.svg",
  },
  {
    name: "JOSM",
    shortName: "JO",
    description:
      "Desktop editor for advanced workflows, validation, plugins, and large mapping sessions.",
    href: "https://josm.openstreetmap.de",
    category: "Editing",
    platforms: ["Windows", "macOS", "Linux"],
    license: "Open source",
    status: "Mature",
    image: "https://josm.openstreetmap.de/favicon.ico",
  },
  {
    name: "Rapid",
    shortName: "RA",
    description:
      "Web editor focused on fast road, building, and point-of-interest editing with assisted data layers.",
    href: "https://rapideditor.org",
    category: "Editing",
    platforms: ["Web"],
    license: "Open source",
    status: "Active",
    image: "https://rapideditor.org/favicon.ico",
  },
  {
    name: "StreetComplete",
    shortName: "SC",
    description:
      "Android quest app that turns local survey gaps into small, approachable mapping tasks.",
    href: "https://streetcomplete.app",
    category: "Mobile mapping",
    platforms: ["Android"],
    license: "Open source",
    status: "Active",
    image: "https://streetcomplete.app/favicon.ico",
  },
  {
    name: "Every Door",
    shortName: "ED",
    description:
      "Mobile field editor for shops, amenities, entrances, building details, and indoor-style surveys.",
    href: "https://every-door.app",
    category: "Mobile mapping",
    platforms: ["Android", "iOS"],
    license: "Open source",
    status: "Active",
    image: "https://every-door.app/favicon.ico",
  },
  {
    name: "Vespucci",
    shortName: "VE",
    description:
      "Full-featured Android editor for detailed geometry and tagging while surveying outdoors.",
    href: "https://vespucci.io",
    category: "Mobile mapping",
    platforms: ["Android"],
    license: "Open source",
    status: "Mature",
    image: "https://vespucci.io/favicon.ico",
  },
  {
    name: "OsmAnd",
    shortName: "OA",
    description:
      "Offline maps, navigation, GPX tools, contour overlays, and mapper-oriented travel features.",
    href: "https://osmand.net",
    category: "Map display",
    platforms: ["Android", "iOS"],
    license: "Mixed",
    status: "Mature",
    image: "https://osmand.net/favicon.ico",
  },
  {
    name: "Organic Maps",
    shortName: "OM",
    description:
      "Fast offline map app for navigation, discovery, bookmarks, and lightweight OSM contribution flows.",
    href: "https://organicmaps.app",
    category: "Map display",
    platforms: ["Android", "iOS"],
    license: "Open source",
    status: "Active",
    image: "https://organicmaps.app/favicon.ico",
  },
  {
    name: "OpenStreetMap Carto",
    shortName: "OC",
    description:
      "Default OSM map style project for tile rendering rules, symbols, labels, and stylesheet work.",
    href: "https://github.com/gravitystorm/openstreetmap-carto",
    category: "Map display",
    platforms: ["Server"],
    license: "Open source",
    status: "Mature",
    image: "https://github.githubassets.com/favicons/favicon.svg",
  },
  {
    name: "MapLibre",
    shortName: "ML",
    description:
      "Open source map rendering libraries and tools for interactive vector maps on web and mobile.",
    href: "https://maplibre.org",
    category: "Developer tools",
    platforms: ["Web", "Android", "iOS"],
    license: "Open source",
    status: "Active",
    image: "https://maplibre.org/favicon.ico",
  },
  {
    name: "Overpass Turbo",
    shortName: "OT",
    description:
      "Query interface for inspecting OSM data, building examples, and sharing Overpass searches.",
    href: "https://overpass-turbo.eu",
    category: "Data services",
    platforms: ["Web"],
    license: "Open source",
    status: "Mature",
    image: "https://overpass-turbo.eu/favicon.ico",
  },
  {
    name: "OSMCha",
    shortName: "OC",
    description:
      "Changeset review system for detecting suspicious edits, organizing validation, and monitoring areas.",
    href: "https://osmcha.org",
    category: "Quality assurance",
    platforms: ["Web"],
    license: "Open source",
    status: "Active",
    image: "https://osmcha.org/favicon.ico",
  },
  {
    name: "MapRoulette",
    shortName: "MR",
    description:
      "Task challenge platform for fixing mapping issues in focused, repeatable review workflows.",
    href: "https://maproulette.org",
    category: "Quality assurance",
    platforms: ["Web"],
    license: "Open source",
    status: "Active",
    image: "https://maproulette.org/favicon.ico",
  },
  {
    name: "uMap",
    shortName: "UM",
    description:
      "Web tool for building shareable thematic maps with OSM basemaps, layers, and annotations.",
    href: "https://umap.openstreetmap.fr",
    category: "Data services",
    platforms: ["Web"],
    license: "Open source",
    status: "Mature",
    image: "https://umap.openstreetmap.fr/static/umap/img/favicon.ico",
  },
  {
    name: "HOT Tasking Manager",
    shortName: "HT",
    description:
      "Humanitarian mapping task manager for dividing projects into reviewable map areas.",
    href: "https://tasks.hotosm.org",
    category: "Data services",
    platforms: ["Web"],
    license: "Open source",
    status: "Specialized",
    image: "https://tasks.hotosm.org/favicon.ico",
  },
  {
    name: "Mapillary",
    shortName: "MA",
    description:
      "Street-level imagery platform used by mappers to inspect signs, roads, turn restrictions, and assets.",
    href: "https://www.mapillary.com",
    category: "Data services",
    platforms: ["Web", "Android", "iOS"],
    license: "Proprietary",
    status: "Specialized",
    image: "https://www.mapillary.com/favicon.ico",
  },
]

const optionMatches = (value: string, selected: string) =>
  selected === ALL || value === selected

const platformMatches = (entry: SoftwareEntry, selected: string) =>
  selected === ALL || entry.platforms.includes(selected)

const searchableText = (entry: SoftwareEntry) =>
  `${entry.name} ${entry.description} ${entry.category} ${entry.platforms.join(
    " ",
  )} ${entry.license} ${entry.status}`.toLowerCase()

const SoftwareLogo = ({ entry }: { entry: SoftwareEntry }) => (
  <div class="software-logo-frame">
    <img
      class="software-logo"
      src={entry.image}
      alt=""
      loading="lazy"
      onError={(event) => {
        event.currentTarget.hidden = true
        event.currentTarget.nextElementSibling?.removeAttribute("hidden")
      }}
    />
    <span
      class="software-logo-fallback"
      hidden
    >
      {entry.shortName}
    </span>
  </div>
)

const FilterSelect = ({
  id,
  label,
  options,
  value,
}: {
  id: string
  label: string
  options: string[]
  value: { value: string }
}) => (
  <label
    class="software-filter"
    for={id}
  >
    <span>{label}</span>
    <select
      id={id}
      class="form-select"
      value={value.value}
      onChange={(event) => (value.value = event.currentTarget.value)}
    >
      <option value={ALL}>{t("site.software.filters.all")}</option>
      {options.map((option) => (
        <option
          key={option}
          value={option}
        >
          {option}
        </option>
      ))}
    </select>
  </label>
)

const SoftwareCard = ({ entry }: { entry: SoftwareEntry }) => (
  <article class="software-card">
    <SoftwareLogo entry={entry} />
    <div class="software-card-body">
      <div class="software-card-heading">
        <h2>{entry.name}</h2>
        <a
          class="btn btn-sm btn-outline-primary"
          href={entry.href}
          rel="noopener"
        >
          <i class="bi bi-box-arrow-up-right me-1" />
          {t("site.software.visit")}
        </a>
      </div>
      <p>{entry.description}</p>
      <div class="software-meta">
        <span>{entry.category}</span>
        {entry.platforms.map((platform) => (
          <span key={platform}>{platform}</span>
        ))}
        <span>{entry.license}</span>
        <span>{entry.status}</span>
      </div>
    </div>
  </article>
)

const SoftwarePage = () => {
  const search = useSignal("")
  const category = useSignal(ALL)
  const platform = useSignal(ALL)
  const license = useSignal(ALL)
  const status = useSignal(ALL)
  const query = search.value.trim().toLowerCase()

  const visibleEntries = softwareEntries.filter(
    (entry) =>
      optionMatches(entry.category, category.value) &&
      platformMatches(entry, platform.value) &&
      optionMatches(entry.license, license.value) &&
      optionMatches(entry.status, status.value) &&
      (query.length === 0 || searchableText(entry).includes(query)),
  )

  return (
    <>
      <div class="content-header">
        <h1 class="container">{t("site.software.title")}</h1>
      </div>
      <div class="content-body">
        <div class="container">
          <div class="software-directory">
            <p class="lead mb-4">{t("site.software.lede")}</p>

            <div class="software-controls">
              <label
                class="software-filter software-search"
                for="software-search"
              >
                <span>{t("site.software.filters.search")}</span>
                <div class="input-group">
                  <span class="input-group-text">
                    <i class="bi bi-search" />
                  </span>
                  <input
                    id="software-search"
                    class="form-control"
                    value={search.value}
                    onInput={(event) => (search.value = event.currentTarget.value)}
                    type="search"
                    autocomplete="off"
                  />
                </div>
              </label>
              <FilterSelect
                id="software-category"
                label={t("site.software.filters.category")}
                options={categories}
                value={category}
              />
              <FilterSelect
                id="software-platform"
                label={t("site.software.filters.platform")}
                options={platforms}
                value={platform}
              />
              <FilterSelect
                id="software-license"
                label={t("site.software.filters.license")}
                options={licenses}
                value={license}
              />
              <FilterSelect
                id="software-status"
                label={t("site.software.filters.status")}
                options={statuses}
                value={status}
              />
            </div>

            <div class="software-result-summary">
              {t("site.software.result_count", { count: visibleEntries.length })}
            </div>

            {visibleEntries.length === 0 ? (
              <div class="software-empty">
                <i class="bi bi-search" />
                <p>{t("site.software.empty")}</p>
              </div>
            ) : (
              <div class="software-grid">
                {visibleEntries.map((entry) => (
                  <SoftwareCard
                    key={entry.name}
                    entry={entry}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  )
}

mountProtoPage(PageSchema, SoftwarePage)
