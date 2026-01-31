import { queryParam } from "@lib/codecs"
import { Time } from "@lib/datetime-inputs"
import { mount } from "@lib/mount"
import {
  GetUserNotesPageRequest_StatusFilter,
  type GetUserNotesPageResponse_SummaryValid,
  NoteService,
  NoteStatus,
} from "@lib/proto/note_pb"
import { StandardPagination } from "@lib/standard-pagination"
import { usePathSuffixSwitch, useQuerySignal } from "@lib/url-signals"
import { isUnmodifiedLeftClick } from "@lib/utils"
import { t } from "i18next"
import { render } from "preact"
import { useId } from "preact/hooks"

type StatusKey = keyof typeof GetUserNotesPageRequest_StatusFilter

const NoteStatusMarker = ({
  status,
  className = "",
}: {
  status: NoteStatus
  className?: string
}) => {
  const marker =
    status === NoteStatus.open
      ? { src: "/static/img/marker/open.webp", alt: t("state.unresolved") }
      : status === NoteStatus.closed
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

const NoteListItem = ({ note }: { note: GetUserNotesPageResponse_SummaryValid }) => {
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

const NotesIndex = ({
  userId,
  displayName,
  avatarUrl,
}: {
  userId: bigint
  displayName: string
  avatarUrl: string
}) => {
  const tab = usePathSuffixSwitch({ created: "", commented: "/commented" })
  const status = useQuerySignal("status", queryParam.enum(["open", "closed"]), {
    defaultValue: "any",
  })

  const statusFilterId = useId()
  const search = status.value === "any" ? "" : `?status=${status.value}`

  const onTabClick = (nextTab: typeof tab.value) => (e: MouseEvent) => {
    if (!isUnmodifiedLeftClick(e)) return
    e.preventDefault()
    tab.value = nextTab
  }

  const commented = tab.value === "commented"

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
                  href={tab.href("created", { search })}
                  class={`nav-link ${commented ? "" : "active"}`}
                  aria-current={commented ? undefined : "page"}
                  onClick={onTabClick("created")}
                >
                  {t("note.user.created_notes")}
                </a>
              </li>
              <li class="nav-item">
                <a
                  href={tab.href("commented", { search })}
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
                    value={status.value}
                    onChange={(e) =>
                      (status.value = e.currentTarget.value as StatusKey)
                    }
                  >
                    <option value="any">{t("state.any")}</option>
                    <option value="open">{t("state.unresolved")}</option>
                    <option value="closed">{t("state.resolved")}</option>
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
              key={`${tab.value}:${status.value}`}
              method={NoteService.method.getUserNotesPage}
              request={{
                userId,
                commented,
                status: GetUserNotesPageRequest_StatusFilter[status.value],
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
}

mount("notes-body", () => {
  const root = document.getElementById("NotesIndex")!
  const { userId, displayName, avatarUrl } = root.dataset

  render(
    <NotesIndex
      userId={BigInt(userId!)}
      displayName={displayName!}
      avatarUrl={avatarUrl!}
    />,
    root,
  )
})
