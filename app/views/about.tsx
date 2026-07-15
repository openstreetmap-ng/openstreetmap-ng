import { PageSchema } from "@proto/about_pb"
import { primaryLanguage } from "@utils/config"
import { i18nLocale } from "@utils/i18n"
import { mountProtoPage } from "@utils/proto-page"

const AboutPage = () => {
  const urlLocale = window.location.pathname.split("/").filter(Boolean)[1]
  const localeOverride =
    urlLocale && urlLocale !== primaryLanguage ? urlLocale : undefined
  const { t, tRich } = i18nLocale(localeOverride)

  const projectName = t("project_name")
  const nameNode = (
    <span class="text-nowrap">
      <img
        class="me-1-5"
        src="/static/img/favicon/256.webp"
        alt={t("alt.logo", { name: projectName })}
        draggable={false}
      />
      <b class="vibrant fw-semibold">{projectName}</b>
    </span>
  )

  return (
    <div class="content-header pb-5">
      <div class="col-lg-10 offset-lg-1 col-xl-8 offset-xl-2 col-xxl-6 offset-xxl-3">
        <div class="row g-0">
          <div class="col-md-6 landing-image">
            <img
              src="/static/img/about/map.webp"
              alt={t("alt.map_layers_art")}
              draggable={false}
            />
            <span class="attribution fs-4">
              © {t("javascripts.map.openstreetmap_contributors")}
            </span>
          </div>
          <div class="col-md-6 landing-text">
            <h2 class="fw-light">
              {tRich("site.about.used_by_html", { name: nameNode })}
            </h2>
          </div>
        </div>

        <div class="header-body">
          <p class="lead mb-4">{t("site.about.lede_text")}</p>

          <h3>
            <i class="bi bi-house-door-fill" />
            {t("site.about.local_knowledge_title")}
          </h3>
          <p>{t("site.about.local_knowledge_html")}</p>

          <h3>
            <i class="bi bi-people-fill" />
            {t("site.about.community_driven_title")}
          </h3>
          <p>
            {tRich("site.about.community_driven_1_html", {
              osm_blog_link: (
                <a href="https://blog.openstreetmap.org">
                  {t("site.about.community_driven_osm_blog")}
                </a>
              ),
              user_diaries_link: (
                <a href="/diary">{t("site.about.community_driven_user_diaries")}</a>
              ),
              community_blogs_link: (
                <a href="https://blogs.openstreetmap.org">
                  {t("site.about.community_driven_community_blogs")}
                </a>
              ),
              osm_foundation_link: (
                <a href="https://osmfoundation.org">
                  {t("site.about.community_driven_osm_foundation")}
                </a>
              ),
            })}
          </p>

          <h3>
            <span class="icon-symbol copyright" />
            {t("site.about.open_data_title")}
          </h3>
          <p>
            {tRich("site.about.open_data_1_html", {
              open_data: <i>{t("site.about.open_data_open_data")}</i>,
              copyright_license_link: (
                <a
                  href="/copyright"
                  rel="license"
                >
                  {t("site.about.open_data_copyright_license")}
                </a>
              ),
            })}
          </p>

        </div>
      </div>
    </div>
  )
}

mountProtoPage(PageSchema, AboutPage)
