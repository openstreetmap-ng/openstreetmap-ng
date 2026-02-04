import { config } from "@lib/config"
import { mainMap } from "@lib/map/main-map"
import { encodeMapState, getInitialMapState } from "@lib/map/state"
import { signal } from "@preact/signals"
import { assertEquals, assertExists } from "@std/assert"
import { runningReduce } from "@std/collections/running-reduce"
import { toSentenceCase } from "@std/text/unstable-to-sentence-case"
import { t } from "i18next"
import { createRef, render } from "preact"
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

const navVisibleCount = signal(navLinks.length)
const navLinksRef = createRef<HTMLDivElement>()
const navLinksListRef = createRef<HTMLUListElement>()
const navLinksMoreRef = createRef<HTMLDivElement>()

const NavbarNav = () => (
  <>
    <div
      class="navbar-links"
      ref={navLinksRef}
    >
      <ul
        class="navbar-nav my-2 my-lg-0"
        ref={navLinksListRef}
      >
        {navLinks.map((link, index) => (
          <li
            key={link.href}
            class="nav-item"
            hidden={index >= navVisibleCount.value}
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

      <div
        class="btn-group"
        hidden={navVisibleCount.value >= navLinks.length}
        ref={navLinksMoreRef}
      >
        <button
          class="btn btn-light btn-bg-initial text-navbar border-0 dropdown-toggle"
          type="button"
          aria-expanded="false"
          data-bs-toggle="dropdown"
        >
          {t("layouts.more")}
        </button>
        <ul class="dropdown-menu dropdown-menu-end">
          {navLinks.slice(navVisibleCount.value).map((link) => (
            <li key={link.href}>
              <a
                class="dropdown-item"
                href={link.href}
                title={link.title}
                rel={link.rel}
              >
                {link.label}
              </a>
            </li>
          ))}
        </ul>
      </div>
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
  const showFindHome = Boolean(mainMap.value && user.homePoint)

  const onFindHomeClick = () => {
    assertExists(user.homePoint)
    location.hash = encodeMapState({
      ...getInitialMapState(),
      lon: user.homePoint.lon,
      lat: user.homePoint.lat,
    })
  }

  return (
    <div class="profile-dropdown dropdown d-flex d-lg-inline-flex">
      <button
        class="btn btn-soft btn-bg-initial dropdown-toggle d-flex align-items-center flex-grow-1"
        type="button"
        aria-expanded="false"
        data-bs-toggle="dropdown"
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
        {showFindHome && (
          <li>
            <button
              class="dropdown-item"
              type="button"
              onClick={onFindHomeClick}
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

const NavbarRight = () => (
  <>
    <NavbarNav />
    <ThemeSwitcher />
    {user ? <NavbarUser /> : <NavbarGuest />}
  </>
)

const configureResponsiveNavbarLinks = (
  container: HTMLDivElement,
  list: HTMLUListElement,
  more: HTMLDivElement,
) => {
  const desktopMedia = window.matchMedia("(min-width: 992px)")
  let linkPrefixWidths: number[] | undefined
  let moreButtonWidth: number | undefined

  const measureLinkWidthsOnce = () => {
    if (linkPrefixWidths !== undefined) return

    const items = list.children
    assertEquals(items.length, navLinks.length)

    const widths = Array.from(items, (el) => el.getBoundingClientRect().width)
    linkPrefixWidths = [0, ...runningReduce(widths, (sum, w) => sum + w, 0)]
  }

  const measureMoreButtonWidthOnce = () => {
    if (moreButtonWidth !== undefined) return

    const prevHidden = more.hidden
    more.hidden = false
    moreButtonWidth = more.getBoundingClientRect().width
    more.hidden = prevHidden
  }

  const getLinksWidth = (count: number) => linkPrefixWidths![count]

  const updateNow = () => {
    if (!desktopMedia.matches) {
      navVisibleCount.value = navLinks.length
      return
    }

    measureLinkWidthsOnce()
    const containerBuffer = 60
    const containerWidth = container.clientWidth - containerBuffer
    const totalWidth = getLinksWidth(navLinks.length)
    if (totalWidth <= containerWidth) {
      navVisibleCount.value = navLinks.length
      return
    }

    measureMoreButtonWidthOnce()
    const availableWithMore = containerWidth - moreButtonWidth!
    let nextCount = 0

    for (let count = navLinks.length - 1; count > 0; count--) {
      if (getLinksWidth(count) <= availableWithMore) {
        nextCount = count
        break
      }
    }

    navVisibleCount.value = nextCount
  }

  let raf = 0
  const update = () => {
    if (raf) return
    raf = requestAnimationFrame(() => {
      raf = 0
      updateNow()
    })
  }

  updateNow()

  const resizeObserver = new ResizeObserver(update)
  resizeObserver.observe(container)
  desktopMedia.addEventListener("change", update)
}

const navbarRightRoot = document.getElementById("NavbarRight")
if (navbarRightRoot) {
  render(<NavbarRight />, navbarRightRoot)
  configureResponsiveNavbarLinks(
    navLinksRef.current!,
    navLinksListRef.current!,
    navLinksMoreRef.current!,
  )
}
