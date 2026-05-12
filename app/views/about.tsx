import { primaryLanguage } from "@lib/config"
import { i18nLocale } from "@lib/i18n"
import { mountProtoPage } from "@lib/proto-page"
import { PageSchema } from "@lib/proto/about_pb"
import { toSentenceCase } from "@std/text/unstable-to-sentence-case"

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

          <h3>
            <span class="icon-symbol section" />
            {t("site.about.legal_title")}
          </h3>
          <p>
            {tRich("site.about.legal_1_1_html", {
              openstreetmap_foundation_link: (
                <a href="https://osmfoundation.org">
                  {t("site.about.legal_1_1_openstreetmap_foundation")}
                </a>
              ),
              terms_of_use_link: (
                <a
                  href="https://osmfoundation.org/wiki/Terms_of_Use"
                  rel="terms-of-service"
                >
                  {t("layouts.tou")}
                </a>
              ),
              aup_link: (
                <a href="https://wiki.openstreetmap.org/wiki/Acceptable_Use_Policy">
                  {t("site.about.legal_1_1_aup")}
                </a>
              ),
              privacy_policy_link: (
                <a
                  href="https://osmfoundation.org/wiki/Privacy_Policy"
                  rel="privacy-policy"
                >
                  {toSentenceCase(t("users.new.privacy_policy"))}
                </a>
              ),
            })}
          </p>
          <p>
            {tRich("site.copyright.legal_babble.trademarks_1_1_html", {
              trademark_policy_link: (
                <a href="https://osmfoundation.org/wiki/Trademark_Policy">
                  {t("site.copyright.legal_babble.trademarks_1_1_trademark_policy")}
                </a>
              ),
            })}
          </p>
          <p>
            {tRich("site.about.legal_2_1_html", {
              contact_the_osmf_link: (
                <a href="https://osmfoundation.org/wiki/Contact">
                  {t("site.about.legal_2_1_contact_the_osmf")}
                </a>
              ),
            })}
          </p>

          <h3>
            <i class="bi bi-heart-fill" />
            {t("site.about.partners_title")}
          </h3>
          <p class="mb-0">
            {tRich("layouts.hosting_partners_html", {
              ucl: <a href="https://www.ucl.ac.uk">{t("layouts.partners_ucl")}</a>,
              fastly: (
                <a href="https://www.fastly.com">{t("layouts.partners_fastly")}</a>
              ),
              bytemark: (
                <a href="https://www.bytemark.co.uk">
                  {t("layouts.partners_bytemark")}
                </a>
              ),
              partners: (
                <a href="https://hardware.openstreetmap.org/thanks/">
                  {t("layouts.partners_partners")}
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
