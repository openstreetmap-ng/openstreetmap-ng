import { PageSchema } from "@proto/about_pb"
import { mountProtoPage } from "@utils/proto-page"
import { t } from "i18next"
import { useMemo, useState } from "preact/hooks"

type SoftwareEntry = {
  name: string
  category: "editors" | "mobile" | "qa" | "maps" | "developer"
  url: string
  description: string
  platforms: string[]
  license: "foss" | "proprietary" | "mixed"
  status: "active" | "maintenance" | "experimental"
}

const SOFTWARE: SoftwareEntry[] = [
  {
    name: "iD",
    category: "editors",
    url: "https://github.com/openstreetmap/iD",
    description: "The friendly web editor built into OpenStreetMap.",
    platforms: ["web"],
    license: "foss",
    status: "active",
  },
  {
    name: "JOSM",
    category: "editors",
    url: "https://josm.openstreetmap.de/",
    description: "A powerful desktop editor for advanced mapping workflows.",
    platforms: ["linux", "macos", "windows"],
    license: "foss",
    status: "active",
  },
  {
    name: "Rapid",
    category: "editors",
    url: "https://rapideditor.org/",
    description: "A web editor focused on assisted mapping and modern editing workflows.",
    platforms: ["web"],
    license: "foss",
    status: "active",
  },
  {
    name: "StreetComplete",
    category: "mobile",
    url: "https://streetcomplete.app/",
    description: "An Android app for solving nearby mapping quests on the ground.",
    platforms: ["android"],
    license: "foss",
    status: "active",
  },
  {
    name: "Every Door",
    category: "mobile",
    url: "https://every-door.app/",
    description: "A mobile editor for shops, amenities, entrances, and addresses.",
    platforms: ["android", "ios"],
    license: "foss",
    status: "active",
  },
  {
    name: "Organic Maps",
    category: "maps",
    url: "https://organicmaps.app/",
    description: "Offline maps and navigation powered by OpenStreetMap data.",
    platforms: ["android", "ios", "linux", "macos", "windows"],
    license: "foss",
    status: "active",
  },
  {
    name: "OsmAnd",
    category: "maps",
    url: "https://osmand.net/",
    description: "Offline maps, navigation, and trip planning with extensive OSM support.",
    platforms: ["android", "ios"],
    license: "mixed",
    status: "active",
  },
  {
    name: "OSMCha",
    category: "qa",
    url: "https://osmcha.org/",
    description: "A quality-assurance tool for reviewing suspicious or interesting changesets.",
    platforms: ["web"],
    license: "foss",
    status: "active",
  },
  {
    name: "Keep Right",
    category: "qa",
    url: "https://www.keepright.at/",
    description: "A long-running tool for finding possible errors in OpenStreetMap data.",
    platforms: ["web"],
    license: "foss",
    status: "maintenance",
  },
  {
    name: "Overpass Turbo",
    category: "developer",
    url: "https://overpass-turbo.eu/",
    description: "A browser IDE for querying OpenStreetMap data with Overpass API.",
    platforms: ["web"],
    license: "foss",
    status: "active",
  },
]

const OPTIONS = {
  category: ["all", "editors", "mobile", "qa", "maps", "developer"],
  platform: ["all", "web", "android", "ios", "linux", "macos", "windows"],
  license: ["all", "foss", "mixed", "proprietary"],
  status: ["all", "active", "maintenance", "experimental"],
} as const

const label = (group: string, value: string) =>
  t(`software.${group}.${value}`, { defaultValue: value })

const SoftwareCard = ({ entry }: { entry: SoftwareEntry }) => (
  <article class="card h-100">
    <div class="card-body d-flex flex-column">
      <div class="d-flex align-items-start justify-content-between gap-2">
        <h2 class="h5 card-title mb-1">{entry.name}</h2>
        <span class="badge text-bg-light border">
          {label("categories", entry.category)}
        </span>
      </div>
      <p class="card-text flex-grow-1">{entry.description}</p>
      <div class="d-flex flex-wrap gap-1 mb-3">
        {entry.platforms.map((platform) => (
          <span
            key={platform}
            class="badge rounded-pill text-bg-secondary"
          >
            {label("platforms", platform)}
          </span>
        ))}
        <span class="badge rounded-pill text-bg-success">
          {label("licenses", entry.license)}
        </span>
        <span class="badge rounded-pill text-bg-info">
          {label("statuses", entry.status)}
        </span>
      </div>
      <a
        class="btn btn-outline-primary align-self-start"
        href={entry.url}
        rel="noopener noreferrer"
        target="_blank"
      >
        {t("software.visit_project")}
      </a>
    </div>
  </article>
)

mountProtoPage(PageSchema, () => {
  const [category, setCategory] = useState("all")
  const [platform, setPlatform] = useState("all")
  const [license, setLicense] = useState("all")
  const [status, setStatus] = useState("all")

  const filtered = useMemo(
    () =>
      SOFTWARE.filter(
        (entry) =>
          (category === "all" || entry.category === category) &&
          (platform === "all" || entry.platforms.includes(platform)) &&
          (license === "all" || entry.license === license) &&
          (status === "all" || entry.status === status),
      ),
    [category, platform, license, status],
  )

  const select = (
    id: string,
    value: string,
    setValue: (value: string) => void,
    values: readonly string[],
    group: string,
  ) => (
    <div class="col-sm-6 col-lg-3">
      <label
        class="form-label"
        for={id}
      >
        {t(`software.filters.${id}`)}
      </label>
      <select
        id={id}
        class="form-select"
        value={value}
        onChange={(e) => setValue(e.currentTarget.value)}
      >
        {values.map((option) => (
          <option value={option}>{label(group, option)}</option>
        ))}
      </select>
    </div>
  )

  return (
    <>
      <div class="content-header">
        <div class="container">
          <h1>{t("software.title")}</h1>
          <p class="lead mb-0">{t("software.description")}</p>
        </div>
      </div>

      <div class="content-body">
        <div class="container">
          <div class="card mb-4">
            <div class="card-body">
              <div class="row g-3">
                {select("category", category, setCategory, OPTIONS.category, "categories")}
                {select("platform", platform, setPlatform, OPTIONS.platform, "platforms")}
                {select("license", license, setLicense, OPTIONS.license, "licenses")}
                {select("status", status, setStatus, OPTIONS.status, "statuses")}
              </div>
            </div>
          </div>

          <div class="row row-cols-1 row-cols-md-2 row-cols-xl-3 g-3">
            {filtered.map((entry) => (
              <div
                key={entry.name}
                class="col"
              >
                <SoftwareCard entry={entry} />
              </div>
            ))}
          </div>

          {!filtered.length && (
            <p class="text-muted mt-4">{t("software.empty")}</p>
          )}
        </div>
      </div>
    </>
  )
})
