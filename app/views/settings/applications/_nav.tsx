import { t } from "i18next"
import { NavLinkItem } from "../_nav"

export const ApplicationsNav = () => (
  <nav>
    <ul class="nav nav-underline gap-2 gap-sm-3 justify-content-around justify-content-sm-start mb-3">
      {[
        {
          href: "/settings/applications",
          label: t("settings.authorizations.title"),
        },
        {
          href: "/settings/applications/admin",
          label: t("settings.my_applications.title"),
          section: true,
        },
        {
          href: "/settings/applications/tokens",
          label: t("settings.my_tokens.title"),
        },
      ].map(({ href, label, section }) => (
        <NavLinkItem
          href={href}
          section={section}
        >
          {label}
        </NavLinkItem>
      ))}
    </ul>
  </nav>
)
