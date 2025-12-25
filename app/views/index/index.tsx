import { getActionSidebar, switchActionSidebar } from "@index/_action-sidebar"
import { searchFormQuery } from "@index/search-form"
import { isLoggedIn } from "@lib/config"
import { tRich } from "@lib/i18n"
import { bannerHidden } from "@lib/local-storage"
import { setPageTitle } from "@lib/title"
import { t } from "i18next"
import type { Map as MaplibreMap } from "maplibre-gl"
import { render } from "preact"

const WelcomeBanner = () => {
  const hidden = bannerHidden("welcome")
  if (hidden.value) return null

  const startMappingHref = isLoggedIn ? "/?edit_help=1" : "/signup"

  return (
    <div
      class="section welcome-banner"
      role="alert"
    >
      <div class="row g-1">
        <div class="col">
          <h2 class="sidebar-title">{t("layouts.intro_header")}</h2>
        </div>
        <div class="col-auto">
          <button
            class="btn-close"
            aria-label={t("javascripts.close")}
            type="button"
            onClick={() => (hidden.value = true)}
          />
        </div>
      </div>

      <p class="fw-light mb-2">{t("layouts.intro_text")}</p>

      <p class="fw-light">
        {tRich("layouts.hosting_partners_html", {
          ucl: () => <a href="https://www.ucl.ac.uk">{t("layouts.partners_ucl")}</a>,
          fastly: () => (
            <a href="https://www.fastly.com">{t("layouts.partners_fastly")}</a>
          ),
          bytemark: () => (
            <a href="https://www.bytemark.co.uk">{t("layouts.partners_bytemark")}</a>
          ),
          partners: () => (
            <a href="https://hardware.openstreetmap.org/thanks/">
              {t("layouts.partners_partners")}
            </a>
          ),
        })}
      </p>

      <div class="row g-2">
        <div class="col">
          <a
            class="btn btn-primary w-100"
            href={startMappingHref}
          >
            {t("layouts.start_mapping")}
          </a>
        </div>
        <div class="col">
          <a
            class="btn btn-outline-primary w-100"
            href="/about"
          >
            {t("layouts.learn_more")}
          </a>
        </div>
      </div>
    </div>
  )
}

const ImageBanner = ({
  name,
  href,
  src,
}: {
  name: string
  href: string
  src: string
}) => {
  const hidden = bannerHidden(name)
  if (hidden.value) return null

  return (
    <div
      class="section image-banner"
      role="alert"
    >
      <a
        href={href}
        target="_blank"
        rel="noopener"
      >
        <img
          src={src}
          draggable={false}
          alt={name}
        />
      </a>
      <div class="btn-close-container">
        <button
          class="btn-close"
          aria-label={t("javascripts.close")}
          type="button"
          onClick={() => (hidden.value = true)}
        />
      </div>
    </div>
  )
}

const IndexSidebar = () => (
  <div class="sidebar-content">
    <WelcomeBanner />
    <ImageBanner
      name="example2"
      href="https://example.com"
      src="/static/img/banner/example2.webp"
    />
  </div>
)

export const getIndexController = (map: MaplibreMap) => {
  const sidebar = getActionSidebar("index")
  render(<IndexSidebar />, sidebar)

  return {
    load: () => {
      switchActionSidebar(map, sidebar)
      setPageTitle()
      searchFormQuery.value = ""
    },
    unload: () => {},
  }
}
