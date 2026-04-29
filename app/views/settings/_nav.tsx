import { isAdministrator } from "@lib/config"
import { isHrefCurrentPage } from "@lib/utils"
import { t } from "i18next"
import type { ComponentChildren } from "preact"

export const NavLinkItem = ({
  href,
  class: className = "",
  section = false,
  children,
}: {
  href: string
  class?: string
  section?: boolean | undefined
  children: ComponentChildren
}) => {
  const active = isHrefCurrentPage(href, { includeSubpaths: section })

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

export const Nav = () => (
  <nav>
    <ul class="nav flex-column settings-nav">
      {[
        {
          href: "/settings",
          icon: "gear",
          label: t("accounts.edit.my settings"),
        },
        {
          href: "/settings/security",
          icon: "shield-lock",
          label: t("settings.password_and_security"),
        },
        {
          href: "/settings/connections",
          icon: "diagram-3",
          label: t("settings.connected_accounts"),
        },
        {
          href: "/settings/applications",
          icon: "boxes",
          label: t("settings.applications"),
          section: true,
        },
      ].map(({ href, icon, label, section }) => (
        <NavLinkItem
          href={href}
          section={section}
        >
          <i class={`bi bi-${icon}`} />
          {label}
        </NavLinkItem>
      ))}

      {isAdministrator && (
        <>
          <li>
            <hr />
          </li>
          {[
            {
              href: "/admin/tasks",
              icon: "list-task",
              label: "Administrative tasks",
            },
            {
              href: "/admin/users",
              icon: "database-gear",
              label: "Users",
              section: true,
            },
            {
              href: "/admin/applications",
              icon: "database-gear",
              label: "Applications",
              section: true,
            },
            {
              href: "/audit",
              icon: "card-checklist",
              label: "Audit logs",
            },
          ].map(({ href, icon, label, section }) => (
            <NavLinkItem
              href={href}
              section={section}
            >
              <i class={`bi bi-${icon}`} />
              {label}
            </NavLinkItem>
          ))}
        </>
      )}

      <li>
        <hr />
      </li>
      {[
        {
          href: "/settings/delete-account",
          icon: "trash",
          label: t("settings.delete_account"),
        },
      ].map(({ href, icon, label }) => (
        <NavLinkItem
          href={href}
          class="text-body-secondary"
        >
          <i class={`bi bi-${icon}`} />
          {label}
        </NavLinkItem>
      ))}
    </ul>
  </nav>
)
