import { queryParam } from "@lib/codecs"
import { Time } from "@lib/datetime-inputs"
import {
  GetUserPageRequest_StatusFilter,
  type GetUserPageResponse_SummaryValid,
  Service,
  Status,
  UserPageSchema,
} from "@lib/proto/note_pb"
import { mountProtoPage } from "@lib/proto-page"
import { defineQueryContract } from "@lib/query-contract"
import { StandardPagination } from "@lib/standard-pagination"
import { usePathSuffixQueryState } from "@lib/url-signals"
import { isUnmodifiedLeftClick } from "@lib/utils"
import { t } from "i18next"
import { useId } from "preact/hooks"

const STATUS_QUERY = defineQueryContract({
  status: queryParam.enum(GetUserPageRequest_StatusFilter, {
    default: GetUserPageRequest_StatusFilter.any,
  }),
})

const NoteStatusMarker = ({
  status,
  className = "",
}: {
  status: Status
  className?: string
}) => {
  const marker =
    status === Status.open
      ? { src: "/static/img/marker/open.webp", alt: t("state.unresolved") }
      : status === Status.closed
        ? { src: "/static/img/marker/closed.webp", alt: t("state.resolved") }
        : { src: "/static/img/marker/hidden.webp", alt: t("state.hidden") }

  return (
    <img
      class={`marker ${className}`}
      src={marker.src}
      alt={marker.alt}
      draggable={false}
    />
  )
}

const NoteListItem = ({ note }: { note: GetUserPageResponse_SummaryValid }) => {
  const wasUpdated = note.updatedAt > note.createdAt
  const numOtherComments = Math.max(0, note.numComments - 1)

  return (
    <li class="row g-2">
      <div class="col-auto">
        <NoteStatusMarker status={note.status} />
      </div>
      <div class="col">
        <div class="social-entry clickable h-100">
          <div class="header text-muted d-flex justify-content-between">
            <div>
              {!note.createdBy ? (
                t("browse.anonymous")
              ) : (
                <a
                  href={`/user/${note.createdBy.displayName}`}
                  rel="author"
                >
                  <img
                    class="avatar"
                    src={note.createdBy.avatarUrl}
                    alt={t("alt.profile_picture")}
                    loading="lazy"
                  />
                  {note.createdBy.displayName}
                </a>
              )}{" "}
              {t("browse.created").toLowerCase()}{" "}
              <Time
                unix={note.createdAt}
                relativeStyle="long"
              />
            </div>
            <div class="row row-cols-md-auto flex-wrap-reverse text-end g-0 g-md-1 g-lg-2">
              {wasUpdated && (
                <>
                  <span>
                    {t("action.updated")}{" "}
                    <Time
                      unix={note.updatedAt}
                      relativeStyle="long"
                    />
                  </span>
                  <span class="d-none d-md-block">·</span>
                </>
              )}
              <a
                class="stretched-link"
                href={`/note/${note.id}`}
              >
                {note.id.toString()}
              </a>
            </div>
          </div>
          <div class="body d-flex justify-content-between">
            <div>{note.body}</div>
            {numOtherComments > 0 ? (
              <div class="num-comments">
                {numOtherComments}
                <i class="bi bi-chat-left-text" />
              </div>
            ) : (
              <div class="num-comments no-comments">
                0
                <i class="bi bi-chat-left" />
              </div>
            )}
          </div>
        </div>
      </div>
    </li>
  )
}

mountProtoPage(UserPageSchema, ({ user: { id: userId, displayName, avatarUrl } }) => {
  const route = usePathSuffixQueryState(
    { created: "", commented: "/commented" },
    STATUS_QUERY,
  )

  const statusFilterId = useId()

  const onTabClick = (nextTab: typeof route.value) => (e: MouseEvent) => {
    if (!isUnmodifiedLeftClick(e)) return
    e.preventDefault()
    route.value = nextTab
  }

  const commented = route.value === "commented"

  return (
    <>
      <div class="content-header pb-0">
        <div class="col-lg-10 offset-lg-1 col-xl-8 offset-xl-2 col-xxl-6 offset-xxl-3">
          <div class="row mb-3">
            <div class="col-auto">
              <img
                class="avatar"
                src={avatarUrl}
                alt={t("alt.profile_picture")}
              />
            </div>
            <div class="col">
              <h1>
                {t("notes.index.heading", {
                  user: displayName,
                })}
              </h1>
              <p class="mb-0">{t("note.user.description")}</p>
            </div>
          </div>

          <nav>
            <ul class="nav nav-tabs nav-tabs-md flex-column flex-md-row">
              <li class="nav-item">
                <a
                  href={route.href("created")}
                  class={`nav-link ${commented ? "" : "active"}`}
                  aria-current={commented ? undefined : "page"}
                  onClick={onTabClick("created")}
                >
                  {t("note.user.created_notes")}
                </a>
              </li>
              <li class="nav-item">
                <a
                  href={route.href("commented")}
                  class={`nav-link ${commented ? "active" : ""}`}
                  aria-current={commented ? "page" : undefined}
                  onClick={onTabClick("commented")}
                >
                  {t("note.user.commented_on_notes")}
                </a>
              </li>
              <li class="nav-item ms-auto">
                <div class="input-group">
                  <label
                    for={statusFilterId}
                    class="input-group-text"
                  >
                    {t("note.user.filter_by_status")}
                  </label>
                  <select
                    id={statusFilterId}
                    class="form-select"
                    autocomplete="off"
                    value={route.query.value.status}
                    onChange={(e) =>
                      (route.query.value = {
                        status: Number(
                          e.currentTarget.value,
                        ) as GetUserPageRequest_StatusFilter,
                      })
                    }
                  >
                    <option value={GetUserPageRequest_StatusFilter.any}>
                      {t("state.any")}
                    </option>
                    <option value={GetUserPageRequest_StatusFilter.open}>
                      {t("state.unresolved")}
                    </option>
                    <option value={GetUserPageRequest_StatusFilter.closed}>
                      {t("state.resolved")}
                    </option>
                  </select>
                </div>
              </li>
            </ul>
          </nav>
        </div>
      </div>

      <div class="content-body">
        <div class="col-lg-10 offset-lg-1 col-xl-8 offset-xl-2 col-xxl-6 offset-xxl-3">
          <div class="notes-pagination">
            <StandardPagination
              method={Service.method.getUserPage}
              request={{
                userId,
                commented,
                status: route.query.value.status,
              }}
              small
              navTop
              navClassBottom="mb-0"
            >
              {(data) => (
                <ul class="notes-list social-list list-unstyled mb-2">
                  {data.notes.length ? (
                    data.notes.map((note) => (
                      <NoteListItem
                        key={note.id}
                        note={note}
                      />
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
      </div>
    </>
  )
})
