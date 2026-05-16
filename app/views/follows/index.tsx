import { Time } from "@components/datetime-inputs"
import { FollowToggleForm } from "@components/follow-toggle-form"
import { StandardPagination } from "@components/standard-pagination"
import { useSignal } from "@preact/signals"
import {
  IndexPageSchema,
  type ListResponse_EntryValid,
  Service,
  Tab,
} from "@proto/follow_pb"
import { isUnmodifiedLeftClick } from "@utils/helpers"
import { mountProtoPage } from "@utils/proto-page"
import { usePathSuffixSwitch } from "@utils/url-signals"
import { t } from "i18next"

const UserRow = ({ entry, tab }: { entry: ListResponse_EntryValid; tab: Tab }) => {
  // The button toggles whether the *current* viewer follows this entry's user.
  // Following tab: we always follow them (Unfollow button).
  // Followers tab: we follow them iff is_following is true (Unfollow), else "Follow back".
  const isFollowing = useSignal(tab === Tab.following ? true : entry.isFollowing)

  return (
    <li class="list-group-item">
      <div class="d-flex align-items-center">
        <a
          href={`/user/${entry.user.displayName}`}
          class="text-decoration-none"
        >
          <img
            src={entry.user.avatarUrl}
            alt={t("alt.profile_picture")}
            class="rounded-circle me-3"
            width={48}
            height={48}
          />
        </a>
        <div class="flex-grow-1">
          <div>
            <a
              href={`/user/${entry.user.displayName}`}
              class="text-decoration-none fw-bold"
            >
              {entry.user.displayName}
            </a>
          </div>
          <small class="text-muted">
            {tab === Tab.followers
              ? t("follows.follower_since")
              : t("follows.following_since")}{" "}
            <Time
              unix={entry.since}
              dateStyle="long"
            />
          </small>
        </div>
        <FollowToggleForm
          targetUserId={entry.user.id}
          isFollowing={isFollowing}
          class={`btn btn-sm ${isFollowing.value ? "btn-outline-secondary" : "btn-primary"}`}
        >
          {({ isFollowing }) =>
            isFollowing ? t("action.unfollow") : t("follows.follow_back")
          }
        </FollowToggleForm>
      </div>
    </li>
  )
}

const EmptyState = ({ tab }: { tab: Tab }) =>
  tab === Tab.followers ? (
    <li class="text-center text-muted py-5">
      <i class="bi bi-people display-1 d-block mb-3" />
      <p>{t("follows.you_dont_have_any_followers_yet")}</p>
    </li>
  ) : (
    <li class="text-center text-muted py-5">
      <i class="bi bi-bookmark display-1 d-block mb-3" />
      <p class="mb-2">{t("follows.you_are_not_following_anyone_yet")}</p>
      <p class="small">{t("follows.visit_user_profiles_to_start")}</p>
    </li>
  )

mountProtoPage(IndexPageSchema, ({ followersCount, followingCount }) => {
  const route = usePathSuffixSwitch(
    { followers: "/followers", following: "/following" },
    { defaultKey: "followers" },
  )
  const onTabClick = (nextTab: typeof route.value) => (e: MouseEvent) => {
    if (!isUnmodifiedLeftClick(e)) return
    e.preventDefault()
    route.value = nextTab
  }
  const tab = route.value === "followers" ? Tab.followers : Tab.following

  return (
    <>
      <div class="content-header pb-0">
        <div class="col-lg-10 offset-lg-1 col-xl-8 offset-xl-2 col-xxl-6 offset-xxl-3">
          <h1>{t("follows.title")}</h1>
          <p>{t("follows.description")}</p>

          <nav>
            <ul class="nav nav-tabs nav-tabs-md flex-column flex-md-row">
              <li class="nav-item">
                <a
                  href={route.href("following")}
                  class={`nav-link ${route.value === "following" ? "active" : ""}`}
                  aria-current={route.value === "following" ? "page" : undefined}
                  onClick={onTabClick("following")}
                >
                  {t("follows.following")}
                  <span class="badge text-bg-secondary ms-2">{followingCount}</span>
                </a>
              </li>
              <li class="nav-item">
                <a
                  href={route.href("followers")}
                  class={`nav-link ${route.value === "followers" ? "active" : ""}`}
                  aria-current={route.value === "followers" ? "page" : undefined}
                  onClick={onTabClick("followers")}
                >
                  {t("follows.followers")}
                  <span class="badge text-bg-secondary ms-2">{followersCount}</span>
                </a>
              </li>
            </ul>
          </nav>
        </div>
      </div>

      <div class="content-body">
        <div class="col-lg-10 offset-lg-1 col-xl-8 offset-xl-2 col-xxl-6 offset-xxl-3">
          <StandardPagination
            method={Service.method.list}
            request={{ tab }}
            urlKey="page"
          >
            {(data) => (
              <ul class="list-unstyled mb-2">
                {data.entries.length ? (
                  data.entries.map((entry) => (
                    <UserRow
                      key={entry.user.id}
                      entry={entry}
                      tab={tab}
                    />
                  ))
                ) : (
                  <EmptyState tab={tab} />
                )}
              </ul>
            )}
          </StandardPagination>
        </div>
      </div>
    </>
  )
})
