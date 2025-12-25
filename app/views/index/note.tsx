import { fromBinary } from "@bufbuild/protobuf"
import {
  getActionSidebar,
  LoadingSpinner,
  SidebarHeader,
  switchActionSidebar,
} from "@index/_action-sidebar"
import { config, isLoggedIn, isModerator } from "@lib/config"
import { Time } from "@lib/datetime-inputs"
import { loadMapImage, NOTE_STATUS_MARKERS } from "@lib/map/image"
import {
  type FocusLayerLayout,
  type FocusLayerPaint,
  focusObjects,
} from "@lib/map/layers/focus-layer"
import {
  NoteCommentPage_Comment_Event as Event,
  type NoteCommentPage_Comment,
  NoteCommentPageSchema,
  type NoteData,
  NoteDataSchema,
  NoteStatus,
} from "@lib/proto/shared_pb"
import { ReportButton } from "@lib/report"
import { configureStandardForm } from "@lib/standard-form"
import { StandardPagination } from "@lib/standard-pagination"
import { setPageTitle } from "@lib/title"
import { type Signal, signal, useSignal, useSignalEffect } from "@preact/signals"
import { assert } from "@std/assert"
import { memoize } from "@std/cache/memoize"
import { t } from "i18next"
import type { Map as MaplibreMap } from "maplibre-gl"
import { render } from "preact"
import { useRef } from "preact/hooks"

const THEME_COLOR = "#f60"
const focusPaint: FocusLayerPaint = {
  "circle-radius": 20,
  "circle-color": THEME_COLOR,
  "circle-opacity": 0.5,
  "circle-stroke-width": 2.5,
  "circle-stroke-color": THEME_COLOR,
}
const focusLayout: FocusLayerLayout = {
  "icon-image": ["get", "icon"],
  "icon-size": 41 / 128,
  "icon-padding": 0,
  "icon-anchor": "bottom",
}

const getEventLabel = memoize((event: Event) => {
  switch (event) {
    case Event.opened:
      return t("action.created")
    case Event.commented:
      return t("action.commented")
    case Event.closed:
      return t("action.resolved")
    case Event.reopened:
      return t("action.reactivated")
    case Event.hidden:
      return t("action.hidden")
  }
})

const NoteComment = ({ comment }: { comment: NoteCommentPage_Comment }) => {
  return (
    <li class="social-entry">
      <p class="header text-muted">
        {comment.user ? (
          <a href={`/user/${comment.user.displayName}`}>
            <img
              class="avatar"
              src={comment.user.avatarUrl}
              alt={t("alt.profile_picture")}
              loading="lazy"
            />
            {comment.user.displayName}
          </a>
        ) : (
          t("browse.anonymous")
        )}{" "}
        {getEventLabel(comment.event)}{" "}
        <Time
          unix={comment.createdAt}
          relativeStyle="long"
        />
      </p>
      {comment.bodyRich ? (
        <div
          class="body pre"
          dangerouslySetInnerHTML={{ __html: comment.bodyRich }}
        />
      ) : (
        <div class="mb-2" />
      )}
    </li>
  )
}

const NoteHeader = ({ data }: { data: NoteData }) => {
  const header = data.header!
  const avatarUrl =
    header.user?.avatarUrl ?? `/api/web/img/avatar/anonymous_note/${data.id}`

  return (
    <div class="social-entry">
      <p class="header text-muted d-flex justify-content-between">
        <span>
          {header.user ? (
            <a
              href={`/user/${header.user.displayName}`}
              rel="author"
            >
              <img
                class="avatar"
                src={avatarUrl}
                alt={t("alt.profile_picture")}
              />
              {header.user.displayName}
            </a>
          ) : (
            <>
              <img
                class="avatar"
                src={avatarUrl}
                alt={t("alt.profile_picture")}
              />
              {t("browse.anonymous")}
            </>
          )}{" "}
          {t("browse.created").toLowerCase()}{" "}
          <Time
            unix={header.createdAt}
            relativeStyle="long"
          />
        </span>
      </p>
      {header.bodyRich && (
        <div
          class="body pre"
          dangerouslySetInnerHTML={{ __html: header.bodyRich }}
        />
      )}
      {!header.user && (
        <div
          class="alert alert-warning mb-2"
          role="alert"
        >
          {t("notes.show.anonymous_warning")}
        </div>
      )}
    </div>
  )
}

const CommentForm = ({
  noteId,
  status,
  onSuccess,
}: {
  noteId: bigint
  status: NoteStatus
  onSuccess: () => void
}) => {
  const formRef = useRef<HTMLFormElement>(null)
  const eventRef = useRef<"hidden" | "closed" | "reopened" | "commented" | null>(null)
  const commentText = useSignal("")

  useSignalEffect(() => {
    const disposeForm = configureStandardForm(
      formRef.current,
      () => {
        formRef.current!.reset()
        onSuccess()
      },
      {
        validationCallback: (formData) => {
          formData.set("event", eventRef.current!)
          return null
        },
      },
    )
    return () => disposeForm?.()
  })

  const hasText = commentText.value.length > 0

  if (status === NoteStatus.open) {
    return (
      <form
        ref={formRef}
        method="POST"
        action={`/api/web/note/${noteId}/comment`}
      >
        <textarea
          class="form-control mb-3"
          name="text"
          rows={5}
          onInput={(e) => (commentText.value = e.currentTarget.value.trim())}
        />
        <div class="row g-1">
          <div class="col">
            {isModerator && (
              <button
                class="btn btn-soft"
                type="submit"
                onClick={() => (eventRef.current = "hidden")}
              >
                {t("notes.show.hide")}
              </button>
            )}
          </div>
          <div class="col-auto">
            <button
              class="btn btn-primary"
              type="submit"
              onClick={() => (eventRef.current = "closed")}
            >
              {hasText ? t("notes.show.comment_and_resolve") : t("notes.show.resolve")}
            </button>
            <button
              class="btn btn-primary ms-1"
              type="submit"
              onClick={() => (eventRef.current = "commented")}
              disabled={!hasText}
            >
              {t("action.comment")}
            </button>
          </div>
        </div>
      </form>
    )
  }

  if (status === NoteStatus.closed) {
    return (
      <form
        ref={formRef}
        method="POST"
        action={`/api/web/note/${noteId}/comment`}
      >
        <div class="row g-1 mt-3">
          <div class="col">
            {isModerator && (
              <button
                class="btn btn-soft"
                type="submit"
                onClick={() => (eventRef.current = "hidden")}
              >
                {t("notes.show.hide")}
              </button>
            )}
          </div>
          <div class="col-auto">
            <button
              class="btn btn-primary"
              type="submit"
              onClick={() => (eventRef.current = "reopened")}
            >
              {t("notes.show.reactivate")}
            </button>
          </div>
        </div>
      </form>
    )
  }

  // hidden status
  return (
    <form
      ref={formRef}
      method="POST"
      action={`/api/web/note/${noteId}/comment`}
    >
      <div class="mt-3">
        <button
          class="btn btn-soft"
          type="submit"
          onClick={() => (eventRef.current = "reopened")}
        >
          {t("action.unhide")}
        </button>
      </div>
    </form>
  )
}

const SubscriptionForm = ({
  noteId,
  isSubscribed,
}: {
  noteId: bigint
  isSubscribed: Signal<boolean>
}) => {
  const formRef = useRef<HTMLFormElement>(null)

  useSignalEffect(() => {
    const disposeForm = configureStandardForm(formRef.current, () => {
      isSubscribed.value = !isSubscribed.value
    })
    return () => disposeForm?.()
  })

  return (
    <form
      ref={formRef}
      class="col-auto subscription-form"
      method="POST"
      action={`/api/web/user-subscription/note/${noteId}/${isSubscribed.value ? "unsubscribe" : "subscribe"}`}
    >
      <button
        class="btn btn-sm btn-soft"
        type="submit"
      >
        {isSubscribed.value && <i class="bi bi-bookmark-check me-1" />}
        {isSubscribed.value
          ? t("javascripts.changesets.show.unsubscribe")
          : t("javascripts.changesets.show.subscribe")}
      </button>
    </form>
  )
}

const NoteSidebar = ({
  map,
  id,
  sidebar,
}: {
  map: MaplibreMap
  id: Signal<string | null>
  sidebar: HTMLElement
}) => {
  const data = useSignal<NoteData | null>(null)
  const loading = useSignal(false)
  const error = useSignal<string | null>(null)
  const refreshKey = useSignal(0)
  const isSubscribed = useSignal(false)

  const reload = () => {
    map.fire("reloadnoteslayer")
    refreshKey.value++
  }

  // Effect: Fetch note data
  useSignalEffect(() => {
    refreshKey.value

    const nid = id.value
    if (!nid) {
      data.value = null
      loading.value = false
      error.value = null
      return
    }

    loading.value = true
    error.value = null
    const abortController = new AbortController()

    fetch(`/api/web/note/${nid}`, { signal: abortController.signal, priority: "high" })
      .then(async (resp) => {
        if (resp.status === 404) {
          error.value = t("browse.not_found.title")
          return
        }
        assert(resp.ok, `${resp.status} ${resp.statusText}`)

        const buffer = await resp.arrayBuffer()
        abortController.signal.throwIfAborted()
        const d = fromBinary(NoteDataSchema, new Uint8Array(buffer))
        data.value = d
        isSubscribed.value = d.isSubscribed

        setPageTitle(`${t("note.title")}: ${nid}`)
      })
      .catch((err) => {
        if (err.name === "AbortError") return
        error.value = err.message
      })
      .finally(() => {
        if (!abortController.signal.aborted) loading.value = false
      })

    return () => abortController.abort()
  })

  // Effect: Map focus
  useSignalEffect(() => {
    const d = data.value
    if (!d) {
      focusObjects(map)
      return
    }

    loadMapImage(map, NOTE_STATUS_MARKERS[d.status])
    focusObjects(
      map,
      [{ type: "note", id: null, geom: [d.lon, d.lat], status: d.status, text: "" }],
      focusPaint,
      focusLayout,
      { padBounds: 0, maxZoom: 15, proportionCheck: false },
    )

    return () => focusObjects(map)
  })

  // Effect: Sidebar visibility
  useSignalEffect(() => {
    if (id.value) switchActionSidebar(map, sidebar)
  })

  const d = data.value

  return (
    <div class="sidebar-content">
      {loading.value && <LoadingSpinner />}
      {error.value && (
        <div
          class="alert alert-danger"
          role="alert"
        >
          {error.value}
        </div>
      )}

      {d && (
        <div class="section">
          {/* Header */}
          <SidebarHeader class="mb-1">
            <h2>
              <span class="sidebar-title me-2">
                {t("note.title")}: {d.id.toString()}
              </span>
              <span
                class={`status-badge badge ${d.status === NoteStatus.closed ? "text-bg-green" : "text-muted bg-body-secondary"}`}
              >
                {d.status === NoteStatus.open && t("state.unresolved")}
                {d.status === NoteStatus.closed && t("state.resolved")}
                {d.status === NoteStatus.hidden && (
                  <>
                    <i class="bi bi-eye-slash-fill" />
                    {t("state.hidden")}
                  </>
                )}
              </span>
            </h2>
          </SidebarHeader>

          <NoteHeader data={d} />

          {/* Location */}
          <p class="location-container mb-0">
            {t("diary_entries.form.location")}:{" "}
            <button
              class="btn btn-link stretched-link"
              type="button"
              onClick={() =>
                map.flyTo({ center: [d.lon, d.lat], zoom: Math.max(map.getZoom(), 15) })
              }
            >
              {`${d.lat.toFixed(5)}, ${d.lon.toFixed(5)}`}
            </button>
          </p>

          {/* Report button */}
          {isLoggedIn && config.userConfig!.id !== d.header?.user?.id && (
            <div class="text-end mt-1 me-1">
              {d.header?.user ? (
                <ReportButton
                  class="btn btn-link btn-sm text-muted p-0"
                  reportType="user"
                  reportTypeId={d.header.user.id}
                  reportAction="user_note"
                  reportActionId={d.id}
                >
                  <i class="bi bi-flag small me-1-5" />
                  {t("report.report_object", { object: t("note.count", { count: 1 }) })}
                </ReportButton>
              ) : (
                <ReportButton
                  class="btn btn-link btn-sm text-muted p-0"
                  reportType="anonymous_note"
                  reportTypeId={d.id}
                  reportAction="generic"
                >
                  <i class="bi bi-flag small me-1-5" />
                  {t("report.report_object", { object: t("note.count", { count: 1 }) })}
                </ReportButton>
              )}
            </div>
          )}

          <div class="mb-4" />

          {/* Discussion header */}
          <div class="row g-1 mb-1">
            <div class="col">
              <h4>{t("browse.changeset.discussion")}</h4>
            </div>
            {isLoggedIn && (
              <SubscriptionForm
                noteId={d.id}
                isSubscribed={isSubscribed}
              />
            )}
          </div>

          {/* Comments pagination */}
          <StandardPagination
            key={`${d.id}-${refreshKey.value}`}
            action={`/api/web/note/${d.id}/comments`}
            label={t("alt.comments_page_navigation")}
            small={true}
            pageOrder="desc"
            protobuf={NoteCommentPageSchema}
          >
            {(page) => (
              <ul class="list-unstyled mb-2">
                {page.comments.map((comment) => (
                  <NoteComment
                    comment={comment}
                    key={comment.createdAt}
                  />
                ))}
              </ul>
            )}
          </StandardPagination>

          {/* Disappear warning */}
          {d.disappearDays !== undefined && (
            <p class="text-center fst-italic mx-4">
              {t("notes.show.disappear_date_html", {
                disappear_in: t("user_blocks.helper.block_duration.days", {
                  count: d.disappearDays,
                }),
              })}
            </p>
          )}

          {/* Comment form or login prompt */}
          {isLoggedIn ? (
            <CommentForm
              noteId={d.id}
              status={d.status}
              onSuccess={reload}
            />
          ) : (
            <div class="text-center">
              <button
                class="btn btn-link"
                type="button"
                data-bs-toggle="modal"
                data-bs-target="#loginModal"
              >
                {t("browse.changeset.join_discussion")}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export const getNoteController = (map: MaplibreMap) => {
  const sidebar = getActionSidebar("note")
  const id = signal<string | null>(null)

  render(
    <NoteSidebar
      map={map}
      id={id}
      sidebar={sidebar}
    />,
    sidebar,
  )

  return {
    load: (matchGroups: Record<string, string>) => {
      id.value = matchGroups.id
    },
    unload: () => {
      id.value = null
    },
  }
}
