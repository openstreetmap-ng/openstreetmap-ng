import { LOCAL_CHAPTERS } from "@lib/config"
import { tRich } from "@lib/i18n"
import { mountProtoPage } from "@lib/proto-page"
import { PageSchema } from "@lib/proto/communities_pb"
import { t } from "i18next"

mountProtoPage(PageSchema, () => (
  <>
    <div class="content-header">
      <h1 class="container">{t("layouts.communities")}</h1>
    </div>
    <div class="content-body">
      <div class="container">
        <p class="lead mb-4">{t("site.communities.lede_text")}</p>

        <h3>{t("site.communities.local_chapters.title")}</h3>
        <p>{t("site.communities.local_chapters.about_text")}</p>
        <p>{t("site.communities.local_chapters.list_text")}</p>
        <ul>
          {LOCAL_CHAPTERS.map(({ id, url }) => (
            <li key={id}>
              <a
                href={url}
                rel="noopener"
                title={t(`osm_community_index.communities.${id}.description`)}
              >
                {t(`osm_community_index.communities.${id}.name`)}
              </a>
            </li>
          ))}
        </ul>

        <h3>{t("site.communities.other_groups.title")}</h3>
        <p>
          {tRich("site.communities.other_groups.other_groups_html", {
            communities_wiki_link: (
              <a href="https://wiki.openstreetmap.org/wiki/User_group">
                {t("site.communities.other_groups.communities_wiki")}
              </a>
            ),
          })}
        </p>
      </div>
    </div>
  </>
))
