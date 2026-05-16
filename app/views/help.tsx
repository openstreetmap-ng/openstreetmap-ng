import { PageSchema } from "@proto/help_pb"
import { mountProtoPage } from "@utils/proto-page"
import { t } from "i18next"
import type { ComponentChildren } from "preact"

const HelpCard = ({
  href,
  title,
  children,
}: {
  href: string
  title: string
  children: ComponentChildren
}) => (
  <div class="col">
    <div class="card h-100">
      <div class="card-body">
        <h5 class="card-title">
          <a
            class="stretched-link"
            href={href}
          >
            {title}
          </a>
        </h5>
        <p class="mb-0">{children}</p>
      </div>
    </div>
  </div>
)

mountProtoPage(PageSchema, () => (
  <>
    <div class="content-header">
      <h1 class="container">{t("site.help.title")}</h1>
    </div>
    <div class="content-body">
      <div class="container">
        <p class="mb-4">{t("site.help.introduction")}</p>

        <div class="row row-cols-1 row-cols-md-2 row-cols-lg-3 g-3">
          <HelpCard
            href="/welcome"
            title={t("site.help.welcome.title")}
          >
            {t("site.help.welcome.description")}
          </HelpCard>
          <HelpCard
            href="https://community.openstreetmap.org"
            title={t("site.help.community.title")}
          >
            {t("site.help.community.description")}
          </HelpCard>
          <HelpCard
            href="https://wiki.openstreetmap.org/wiki/Beginners%27_guide"
            title={t("site.help.beginners_guide.title")}
          >
            {t("site.help.beginners_guide.description")}
          </HelpCard>
          <HelpCard
            href="https://wiki.openstreetmap.org"
            title={t("site.help.wiki.title")}
          >
            {t("site.help.wiki.description")}
          </HelpCard>
          <HelpCard
            href="https://lists.openstreetmap.org"
            title={t("site.help.mailing_lists.title")}
          >
            {t("site.help.mailing_lists.description")}
          </HelpCard>
          <HelpCard
            href="https://irc.openstreetmap.org"
            title={t("site.help.irc.title")}
          >
            {t("site.help.irc.description")}
          </HelpCard>
          <HelpCard
            href="https://welcome.openstreetmap.org"
            title={t("site.help.welcomemat.title")}
          >
            {t("site.help.welcomemat.description")}
          </HelpCard>
          <HelpCard
            href="https://switch2osm.org"
            title={t("site.help.switch2osm.title")}
          >
            {t("site.help.switch2osm.description")}
          </HelpCard>
        </div>
      </div>
    </div>
  </>
))
