import { config, isLoggedIn, primaryLanguage } from "@lib/config"
import { getLocaleDisplayNameByCode } from "@lib/locale"
import type { UserValid } from "@lib/proto/shared_pb"
import { t } from "i18next"

export enum DiaryTab {
  all,
  primary_language,
  other_language,
  self,
  profile,
}

export const Nav = ({
  activeTab,
  language,
  user: userProp,
}: {
  activeTab: DiaryTab
  language: string | undefined
  user: UserValid | undefined
}) => {
  const currentUser = config.userConfig?.user
  const user = userProp ?? (activeTab === DiaryTab.self ? currentUser : undefined)
  const baseUrl =
    activeTab === DiaryTab.self
      ? `/user/${currentUser!.displayName}/diary`
      : user
        ? `/user/${user.displayName}/diary`
        : "/diary"
  const rssUrl = language ? `${baseUrl}/${language}/rss` : `${baseUrl}/rss`

  return (
    <nav>
      <ul class="nav nav-tabs nav-tabs-md flex-column flex-md-row">
        {[
          {
            href: "/diary",
            label: t("diary.all_diaries"),
            active: activeTab === DiaryTab.all,
          },
          {
            href: `/diary/${primaryLanguage}`,
            label: t("diary.only_in_language", {
              language: getLocaleDisplayNameByCode(primaryLanguage),
            }),
            active: activeTab === DiaryTab.primary_language,
          },
          ...(activeTab === DiaryTab.other_language
            ? [
                {
                  href: `/diary/${language!}`,
                  label: t("diary.only_in_language", {
                    language: getLocaleDisplayNameByCode(language!),
                  }),
                  active: true,
                },
              ]
            : []),
          ...(currentUser
            ? [
                {
                  href: `/user/${currentUser.displayName}/diary`,
                  label: t("diary_entries.index.my_diary"),
                  active: activeTab === DiaryTab.self,
                },
              ]
            : []),
          ...(activeTab === DiaryTab.profile
            ? [
                {
                  href: `/user/${user!.displayName}/diary`,
                  label: t("diary_entries.index.user_title", {
                    user: user!.displayName,
                  }),
                  active: true,
                },
              ]
            : []),
        ].map(({ href, label, active }) => (
          <li class="nav-item">
            <a
              href={href}
              class={`nav-link ${active ? "active" : ""}`}
              aria-current={active ? "page" : undefined}
            >
              {label}
            </a>
          </li>
        ))}
        <li class="nav-item ms-auto">
          {isLoggedIn && (
            <a
              class="btn btn-soft me-1"
              href="/diary/new"
            >
              <i class="bi bi-journal-plus me-2" />
              {t("diary.new_entry")}
            </a>
          )}
          <a
            class="btn btn-soft"
            href={rssUrl}
            aria-label={t("alt.rss_feed")}
          >
            <i class="bi bi-rss-fill rss-color" />
          </a>
        </li>
      </ul>
    </nav>
  )
}
