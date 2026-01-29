import { SidebarContent, SidebarHeader, useSidebarRpc } from "@index/_action-sidebar"
import { defineRoute } from "@index/router"
import { routeParam } from "@lib/codecs"
import {
  config,
  isLoggedIn,
  isModerator,
  NOTE_COMMENT_BODY_MAX_LENGTH,
} from "@lib/config"
import { Time } from "@lib/datetime-inputs"
import { loadMapImage, NOTE_STATUS_MARKERS } from "@lib/map/image"
import {
  type FocusLayerLayout,
  type FocusLayerPaint,
  focusObjects,
} from "@lib/map/layers/focus-layer"
import {
  type AddNoteCommentResponseValid,
  GetNoteCommentsResponse_Comment_Event as Event,
  type GetNoteCommentsResponse_CommentValid,
  type GetNoteCommentsResponseValid,
  type NoteDataValid,
  NoteService,
  NoteStatus,
} from "@lib/proto/note_pb"
import { ReportButton } from "@lib/report"
import { StandardForm } from "@lib/standard-form"
import { StandardPagination } from "@lib/standard-pagination"
import { setPageTitle } from "@lib/title"
import {
  type ReadonlySignal,
  type Signal,
  useComputed,
  useSignal,
  useSignalEffect,
} from "@preact/signals"
import { memoize } from "@std/cache/memoize"
import { t } from "i18next"
import type { Map as MaplibreMap } from "maplibre-gl"

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

const NoteComment = ({
  comment,
}: {
  comment: GetNoteCommentsResponse_CommentValid
}) => {
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

const NoteHeader = ({ data }: { data: NoteDataValid }) => {
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

type CommentResult = {
  result: AddNoteCommentResponseValid
  reloadnoteslayer: boolean
}

const CommentForm = ({
  noteId,
  status,
  onSuccess,
}: {
  noteId: bigint
  status: NoteStatus
  onSuccess: (result: CommentResult) => void
}) => {
  const commentText = useSignal("")

  const hasText = commentText.value.length > 0

  const buildRequest = ({ formData }: { formData: FormData }) => ({
    id: noteId,
    event: Event[formData.get("event")! as keyof typeof Event],
    body: formData.get("body")!.toString(),
  })

  if (status === NoteStatus.open) {
    return (
      <StandardForm
        method={NoteService.method.addNoteComment}
        buildRequest={buildRequest}
        resetOnSuccess
        onSuccess={(result, ctx) => {
          commentText.value = ""
          onSuccess({
            result,
            reloadnoteslayer: ctx.request.event !== Event.commented,
          })
        }}
      >
        <textarea
          class="form-control mb-3"
          name="body"
          rows={5}
          maxLength={NOTE_COMMENT_BODY_MAX_LENGTH}
          onInput={(e) => (commentText.value = e.currentTarget.value.trim())}
        />
        <div class="row g-1">
          <div class="col">
            {isModerator && (
              <button
                class="btn btn-soft"
                type="submit"
                name="event"
                value="hidden"
              >
                {t("notes.show.hide")}
              </button>
            )}
          </div>
          <div class="col-auto">
            <button
              class="btn btn-primary"
              type="submit"
              name="event"
              value="closed"
            >
              {hasText ? t("notes.show.comment_and_resolve") : t("notes.show.resolve")}
            </button>
            <button
              class="btn btn-primary ms-1"
              type="submit"
              name="event"
              value="commented"
              disabled={!hasText}
            >
              {t("action.comment")}
            </button>
          </div>
        </div>
      </StandardForm>
    )
  }

  if (status === NoteStatus.closed) {
    return (
      <StandardForm
        method={NoteService.method.addNoteComment}
        buildRequest={buildRequest}
        resetOnSuccess
        onSuccess={(result, ctx) => {
          onSuccess({
            result,
            reloadnoteslayer: ctx.request.event !== Event.commented,
          })
        }}
      >
        <div class="row g-1 mt-3">
          <div class="col">
            {isModerator && (
              <button
                class="btn btn-soft"
                type="submit"
                name="event"
                value="hidden"
              >
                {t("notes.show.hide")}
              </button>
            )}
          </div>
          <div class="col-auto">
            <button
              class="btn btn-primary"
              type="submit"
              name="event"
              value="reopened"
            >
              {t("notes.show.reactivate")}
            </button>
          </div>
        </div>
      </StandardForm>
    )
  }

  // hidden status
  return (
    <StandardForm
      method={NoteService.method.addNoteComment}
      buildRequest={buildRequest}
      resetOnSuccess
      onSuccess={(result, ctx) => {
        onSuccess({
          result,
          reloadnoteslayer: ctx.request.event !== Event.commented,
        })
      }}
    >
      <div class="mt-3">
        <button
          class="btn btn-soft"
          type="submit"
          name="event"
          value="reopened"
        >
          {t("action.unhide")}
        </button>
      </div>
    </StandardForm>
  )
}

const SubscriptionForm = ({
  noteId,
  isSubscribed,
}: {
  noteId: bigint
  isSubscribed: Signal<boolean>
}) => {
  return (
    <StandardForm
      class="col-auto subscription-form"
      method={NoteService.method.setNoteSubscription}
      buildRequest={() => ({ id: noteId, isSubscribed: !isSubscribed.value })}
      onSuccess={(resp) => (isSubscribed.value = resp.isSubscribed)}
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
    </StandardForm>
  )
}

const NoteSidebar = ({ map, id }: { map: MaplibreMap; id: ReadonlySignal<bigint> }) => {
  const isSubscribed = useSignal(false)
  const preloadedComments = useSignal<GetNoteCommentsResponseValid | null>(null)

  const { resource, data } = useSidebarRpc(
    useComputed(() => ({ id: id.value })),
    NoteService.method.getNote,
    (r) => r.note,
  )

  // Effect: Sync derived state
  useSignalEffect(() => {
    const r = resource.value
    if (r.tag === "not-found") {
      setPageTitle(t("browse.not_found.title"))
    } else if (r.tag === "ready") {
      const d = r.data
      isSubscribed.value = d.isSubscribed
      setPageTitle(`${t("note.title")}: ${d.id}`)
    }
  })

  // Effect: Map focus
  useSignalEffect(() => {
    const d = data.value
    if (!d) return

    loadMapImage(map, NOTE_STATUS_MARKERS[d.status])
    focusObjects(
      map,
      [
        {
          type: "note",
          id: null,
          geom: [d.location.lon, d.location.lat],
          status: d.status,
          body: "",
        },
      ],
      focusPaint,
      focusLayout,
      { padBounds: 0, maxZoom: 15, minProportion: 0 },
    )

    return () => focusObjects(map)
  })

  return (
    <SidebarContent
      resource={resource}
      notFound={() =>
        t("browse.not_found.sorry", {
          type: t("note.title").toLowerCase(),
          id: id.toString(),
        })
      }
    >
      {(d) => (
        <div class="section">
          {/* Header */}
          <SidebarHeader class="mb-1">
            <h2>
              <span class="sidebar-title me-2">
                {t("note.title")}: {d.id}
              </span>
              <span
                class={`status-badge badge ${d.status === NoteStatus.closed ? "text-bg-green" : "text-muted bg-body-secondary"}`}
              >
                {d.status === NoteStatus.open && t("state.unresolved")}
                {d.status === NoteStatus.closed && t("state.resolved")}
                {d.status === NoteStatus.hidden && (
                  <>
                    <i class="bi bi-eye-slash-fill me-1-5" />
                    {t("state.hidden")}
                  </>
                )}
              </span>
            </h2>
          </SidebarHeader>

          <NoteHeader data={d} />

          {/* Location */}
          <p class="location-container mb-0">
            {t("diary_entries.form.location")}:
            <button
              class="btn btn-link stretched-link"
              type="button"
              onClick={() =>
                map.flyTo({
                  center: [d.location.lon, d.location.lat],
                  zoom: Math.max(map.getZoom(), 15),
                })
              }
            >
              {`${d.location.lat.toFixed(5)}, ${d.location.lon.toFixed(5)}`}
            </button>
          </p>

          {/* Report button */}
          {isLoggedIn && config.userConfig!.id !== d.header!.user?.id && (
            <div class="text-end mt-1 me-1">
              {d.header!.user ? (
                <ReportButton
                  class="btn btn-link btn-sm text-muted p-0"
                  reportType="user"
                  reportTypeId={d.header!.user.id}
                  reportAction="user_note"
                  reportActionId={d.id}
                >
                  <i class="bi bi-flag small me-1-5" />
                  {t("report.report_object", {
                    object: t("note.count", { count: 1 }),
                  })}
                </ReportButton>
              ) : (
                <ReportButton
                  class="btn btn-link btn-sm text-muted p-0"
                  reportType="anonymous_note"
                  reportTypeId={d.id}
                  reportAction="generic"
                >
                  <i class="bi bi-flag small me-1-5" />
                  {t("report.report_object", {
                    object: t("note.count", { count: 1 }),
                  })}
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
            key={d.id}
            method={NoteService.method.getNoteComments}
            request={{ id: d.id }}
            label={t("alt.comments_page_navigation")}
            small
            pageOrder="desc"
            responseSignal={preloadedComments}
          >
            {(page) => (
              <ul class="list-unstyled mb-2">
                {page.comments.map((comment) => (
                  <NoteComment
                    key={comment.createdAt}
                    comment={comment}
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
              onSuccess={({ result, reloadnoteslayer }) => {
                resource.value = { tag: "ready", data: result.note }
                preloadedComments.value = result.comments
                if (reloadnoteslayer) map.fire("reloadnoteslayer")
              }}
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
    </SidebarContent>
  )
}

export const NoteRoute = defineRoute({
  id: "note",
  path: ["/note/:id", "/note/:id/unsubscribe"],
  params: { id: routeParam.positive() },
  Component: NoteSidebar,
})
