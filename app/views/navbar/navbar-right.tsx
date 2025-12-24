import { config } from "@lib/config"
import { signal } from "@preact/signals"
import { assertExists } from "@std/assert"
import { toSentenceCase } from "@std/text/unstable-to-sentence-case"
import { t } from "i18next"
import { render } from "preact"
import { LanguageSwitcher } from "./_language-switcher"
import { ThemeSwitcher } from "./_theme-switcher"

const navLinks = [
  {
    href: "/traces",
    label: t("layouts.gps_traces"),
    title: t("layouts.gps_traces_tooltip"),
  },
  {
    href: "/diary",
    label: t("layouts.user_diaries"),
    title: t("layouts.user_diaries_tooltip"),
  },
  {
    href: "/communities",
    label: t("site.communities.title"),
  },
  {
    href: "/copyright",
    label: t("layouts.copyright"),
    rel: "license",
  },
  {
    href: "/help",
    label: t("layouts.help"),
  },
  {
    href: "/about",
    label: t("layouts.about"),
  },
]

const NavbarNav = () => (
  <>
    <ul class="navbar-nav my-2 my-lg-0">
      {navLinks.map((link) => (
        <li
          class="nav-item"
          key={link.href}
        >
          <a
            class="nav-link"
            href={link.href}
            title={link.title}
            rel={link.rel}
          >
            {link.label}
          </a>
        </li>
      ))}
    </ul>

    <div class="btn-group navbar-nav-more d-none">
      <button
        class="btn btn-light btn-bg-initial text-navbar border-0 dropdown-toggle"
        type="button"
        data-bs-toggle="dropdown"
        aria-expanded="false"
      >
        {t("layouts.more")}
      </button>
      <ul class="dropdown-menu dropdown-menu-end" />
    </div>
  </>
)

const user = config.userConfig
export const messagesCountUnread = signal(user?.messagesCountUnread ?? 0)
const reportsCountModerator = user?.reportsCountModerator ?? 0
const reportsCountAdministrator = user?.reportsCountAdministrator ?? 0

const NavbarUser = () => {
  assertExists(user)
  const showBadges = Boolean(
    messagesCountUnread.value || reportsCountModerator || reportsCountAdministrator,
  )
  const showReports = Boolean(reportsCountModerator || reportsCountAdministrator)

  return (
    <div class="profile-dropdown dropdown d-flex d-lg-inline-flex">
      <button
        class="profile-btn btn btn-soft btn-bg-initial dropdown-toggle d-flex align-items-center flex-grow-1"
        type="button"
        data-bs-toggle="dropdown"
        aria-expanded="false"
      >
        <img
          class="avatar me-2"
          src={user.avatarUrl}
          alt={t("alt.profile_picture")}
        />
        <span
          class="profile-name me-auto"
          title={user.displayName}
        >
          {user.displayName}
        </span>
        {showBadges && (
          <span class="d-inline-flex gap-1 ms-2">
            <span class="badge text-bg-light-green">
              {messagesCountUnread.value || ""}
            </span>
            <span class="badge text-bg-primary">{reportsCountModerator || ""}</span>
            <span class="badge text-bg-danger">{reportsCountAdministrator || ""}</span>
          </span>
        )}
      </button>
      <ul class="dropdown-menu dropdown-menu-green dropdown-menu-end">
        <li>
          <a
            class="dropdown-item"
            href="/dashboard"
          >
            {t("dashboards.show.title")}
          </a>
        </li>
        <li>
          <a
            class="dropdown-item d-flex align-items-center"
            href="/messages/inbox"
          >
            {t("users.show.my messages")}
            <span class="badge text-bg-light-green ms-2">
              {messagesCountUnread.value}
            </span>
          </a>
        </li>
        <li>
          <a
            class="dropdown-item"
            href={`/user/${user.displayName}`}
          >
            {t("users.show.my profile")}
          </a>
        </li>
        <li>
          <a
            class="dropdown-item"
            href="/settings"
          >
            {t("accounts.edit.my settings")}
          </a>
        </li>
        {showReports && (
          <>
            <li>
              <hr class="dropdown-divider" />
            </li>
            <li>
              <a
                class="dropdown-item d-flex align-items-center"
                href="/reports"
              >
                Reports
                <span class="d-inline-flex gap-1 ms-auto">
                  <span class="badge text-bg-primary">
                    {reportsCountModerator || ""}
                  </span>
                  <span class="badge text-bg-danger">
                    {reportsCountAdministrator || ""}
                  </span>
                </span>
              </a>
            </li>
          </>
        )}
        <li>
          <hr class="dropdown-divider" />
        </li>
        {user.homePoint && (
          <li class="find-home-container d-none">
            <button
              class="dropdown-item"
              type="button"
            >
              {t("layouts.home")}
            </button>
          </li>
        )}
        <li>
          <form
            method="POST"
            action="/api/web/user/logout"
          >
            <button
              class="dropdown-item"
              type="submit"
            >
              {t("layouts.logout")}
            </button>
          </form>
        </li>
      </ul>
    </div>
  )
}

const NavbarGuest = () => (
  <>
    <fieldset class="btn-group d-flex d-lg-inline-flex">
      <button
        class="btn btn-soft text-navbar fw-medium"
        type="button"
        data-bs-toggle="modal"
        data-bs-target="#loginModal"
      >
        {t("login.sign_in")}
      </button>
      <a
        class="btn btn-soft text-navbar fw-medium"
        href="/signup"
      >
        {toSentenceCase(t("users.new.title"))}
      </a>
    </fieldset>

    <LanguageSwitcher />
  </>
)

const NavbarRight = () => {
  return (
    <>
      <NavbarNav />
      <ThemeSwitcher />
      {user ? <NavbarUser /> : <NavbarGuest />}
    </>
  )
}

render(<NavbarRight />, document.getElementById("NavbarRight")!)
