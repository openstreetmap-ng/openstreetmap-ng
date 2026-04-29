import { Time } from "@lib/datetime-inputs"
import {
  type GetUserCommentsPageResponseValid,
  Service,
  UserCommentsPageSchema,
} from "@lib/proto/diary_pb"
import { mountProtoPage } from "@lib/proto-page"
import { StandardPagination } from "@lib/standard-pagination"
import { t } from "i18next"

mountProtoPage(UserCommentsPageSchema, ({ user }) => (
  <>
    <div class="content-header">
      <div class="col-lg-10 offset-lg-1 col-xl-8 offset-xl-2 col-xxl-6 offset-xxl-3">
        <h1>{t("diary_entries.comments.heading", { user: user.displayName })}</h1>
        <p class="mb-1-5">{t("diary.user_comments.description")}</p>
      </div>
    </div>

    <div class="content-body">
      <div class="col-lg-10 offset-lg-1 col-xl-8 offset-xl-2 col-xxl-6 offset-xxl-3">
        <StandardPagination
          method={Service.method.getUserCommentsPage}
          request={{ userId: user.id }}
          urlKey="page"
          navTop
          navClassBottom="mb-0"
          ariaLabel={t("alt.comments_page_navigation")}
        >
          {(data: GetUserCommentsPageResponseValid) => (
            <ul class="diary-user-comments-list social-list list-unstyled mb-2">
              {data.entries.length ? (
                data.entries.map((entry) => (
                  <li
                    key={entry.id}
                    class="social-entry clickable"
                  >
                    <p class="header text-muted">
                      <a href={`/user/${user.displayName}`}>
                        <img
                          class="avatar"
                          src={user.avatarUrl}
                          alt={t("alt.profile_picture")}
                        />
                        {user.displayName}
                      </a>{" "}
                      {t("action.commented")}{" "}
                      <Time
                        unix={entry.createdAt}
                        relativeStyle="long"
                      />
                      <a
                        class="stretched-link"
                        href={`/diary/${entry.diaryId}#comment${entry.id}`}
                      >
                        <span class="visually-hidden">
                          {t("diary.comments")} {entry.id}
                        </span>
                      </a>
                    </p>
                    <div class="rich-text body">
                      <h5>
                        <a href={`/diary/${entry.diaryId}`}>{entry.diaryTitle}</a>
                      </h5>
                      <div dangerouslySetInnerHTML={{ __html: entry.bodyRich }} />
                    </div>
                  </li>
                ))
              ) : (
                <li>
                  <h3>{t("traces.index.empty_title")}</h3>
                </li>
              )}
            </ul>
          )}
        </StandardPagination>
      </div>
    </div>
  </>
))
