import { t } from "i18next"
import { NavLinkItem } from "../_nav"

export const SettingsApplicationsNav = () => (
  <nav>
    <ul class="nav nav-underline gap-2 gap-sm-3 justify-content-around justify-content-sm-start mb-3">
      <NavLinkItem href="/settings/applications">
        {t("settings.authorizations.title")}
      </NavLinkItem>
      <NavLinkItem href="/settings/applications/admin">
        {t("settings.my_applications.title")}
      </NavLinkItem>
      <NavLinkItem href="/settings/applications/tokens">
        {t("settings.my_tokens.title")}
      </NavLinkItem>
    </ul>
  </nav>
)
