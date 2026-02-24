import { isAdministrator } from "@lib/config"
import { isHrefCurrentPage } from "@lib/utils"
import { t } from "i18next"
import type { ComponentChildren } from "preact"

export const NavLinkItem = ({
  href,
  class: className = "",
  children,
}: {
  href: string
  class?: string
  children: ComponentChildren
}) => {
  const active = isHrefCurrentPage(href)

  return (
    <li class="nav-item">
      <a
        class={`nav-link ${className} ${active ? "active" : ""}`}
        href={href}
        aria-current={active ? "page" : undefined}
      >
        {children}
      </a>
    </li>
  )
}

export const SettingsNav = () => (
  <nav>
    <ul class="nav flex-column settings-nav">
      <NavLinkItem href="/settings">
        <i class="bi bi-gear" />
        {t("accounts.edit.my settings")}
      </NavLinkItem>
      <NavLinkItem href="/settings/security">
        <i class="bi bi-shield-lock" />
        {t("settings.password_and_security")}
      </NavLinkItem>
      <NavLinkItem href="/settings/connections">
        <i class="bi bi-diagram-3" />
        {t("settings.connected_accounts")}
      </NavLinkItem>
      <NavLinkItem href="/settings/applications">
        <i class="bi bi-boxes" />
        {t("settings.applications")}
      </NavLinkItem>

      {isAdministrator && (
        <>
          <li>
            <hr />
          </li>
          <NavLinkItem href="/admin/tasks">
            <i class="bi bi-list-task" />
            Administrative tasks
          </NavLinkItem>
          <NavLinkItem href="/admin/users">
            <i class="bi bi-database-gear" />
            Users
          </NavLinkItem>
          <NavLinkItem href="/admin/applications">
            <i class="bi bi-database-gear" />
            Applications
          </NavLinkItem>
          <NavLinkItem href="/audit">
            <i class="bi bi-card-checklist" />
            Audit logs
          </NavLinkItem>
        </>
      )}

      <li>
        <hr />
      </li>
      <NavLinkItem
        href="/settings/delete-account"
        class="text-body-secondary"
      >
        <i class="bi bi-trash" />
        {t("settings.delete_account")}
      </NavLinkItem>
    </ul>
  </nav>
)
