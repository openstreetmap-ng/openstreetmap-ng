import { SidebarContent, SidebarHeader, useSidebar } from "@index/_action-sidebar"
import { ElementsListRow, ElementsSection, getElementTypeLabel } from "@index/element"
import { defineRoute } from "@index/router"
import { routeParam } from "@lib/codecs"
import {
  API_URL,
  CHANGESET_COMMENT_BODY_MAX_LENGTH,
  config,
  isLoggedIn,
} from "@lib/config"
import { Time } from "@lib/datetime-inputs"
import { useDisposeSignalEffect } from "@lib/dispose-scope"
import { makeBoundsMinimumSize } from "@lib/map/bounds"
import { type FocusLayerPaint, focusObjects } from "@lib/map/layers/focus-layer"
import {
  type AddChangesetCommentResponseValid,
  type ChangesetDataValid,
  ChangesetService,
  type ChangesetData_Element as Element,
  type GetChangesetCommentsResponse_CommentValid,
  type GetChangesetCommentsResponseValid,
} from "@lib/proto/changeset_pb"
import { ElementType } from "@lib/proto/shared_pb"
import { ReportButton } from "@lib/report"
import { StandardForm } from "@lib/standard-form"
import { StandardPagination } from "@lib/standard-pagination"
import { Tags } from "@lib/tags"
import { setPageTitle } from "@lib/title"
import type { OSMChangeset } from "@lib/types"
import {
  type ReadonlySignal,
  type Signal,
  useComputed,
  useSignal,
  useSignalEffect,
} from "@preact/signals"
import { t } from "i18next"
import type { Map as MaplibreMap } from "maplibre-gl"

const focusPaint: FocusLayerPaint = {
  "fill-opacity": 0,
  "line-color": "#f90",
  "line-opacity": 1,
  "line-width": 3,
}

export const ChangesetStats = ({
  numCreate,
  numModify,
  numDelete,
}: {
  numCreate: number
  numModify: number
  numDelete: number
}) => (
  <div class="changeset-stats">
    {numCreate > 0 && <span class="stat-create">{numCreate}</span>}
    {numModify > 0 && <span class="stat-modify">{numModify}</span>}
    {numDelete > 0 && <span class="stat-delete">{numDelete}</span>}
  </div>
)

const getChangesetElementsTitle = (type: ElementType) => {
  if (type === ElementType.node)
    // @ts-expect-error - i18next pluralization
    return (count: string) => t("browse.changeset.node", { count })
  if (type === ElementType.way)
    // @ts-expect-error - i18next pluralization
    return (count: string) => t("browse.changeset.way", { count })
  // @ts-expect-error - i18next pluralization
  return (count: string) => t("browse.changeset.relation", { count })
}

const ChangesetHeader = ({ data }: { data: ChangesetDataValid }) => {
  const isOpen = data.closedAt === undefined
  return (
    <div class="changesets-list social-list mb-3">
      <div class="social-entry">
        <p class="header text-muted d-flex justify-content-between">
          <span>
            {data.user ? (
              <a
                href={`/user/${data.user.displayName}`}
                rel="author"
              >
                <img
                  class="avatar"
                  src={data.user.avatarUrl}
                  alt={t("alt.profile_picture")}
                  loading="lazy"
                />
                {data.user.displayName}
              </a>
            ) : (
              t("browse.anonymous")
            )}{" "}
            {isOpen
              ? t("browse.created").toLowerCase()
              : t("browse.closed").toLowerCase()}{" "}
            <Time
              unix={isOpen ? data.createdAt : data.closedAt!}
              relativeStyle="long"
            />
          </span>
          {isOpen && (
            <span
              class="badge open-indicator"
              title={t("changeset.this_changeset_is_state", {
                state: t("changeset.open").toLowerCase(),
              })}
            >
              <i class="bi bi-pencil-square me-1" />
              {t("changeset.open")}
            </span>
          )}
        </p>
        <div class="body">
          <span dangerouslySetInnerHTML={{ __html: data.commentRich }} />
          <ChangesetStats
            numCreate={data.numCreate}
            numModify={data.numModify}
            numDelete={data.numDelete}
          />
        </div>
      </div>
    </div>
  )
}

const SubscriptionForm = ({
  changesetId,
  isSubscribed,
}: {
  changesetId: bigint
  isSubscribed: Signal<boolean>
}) => (
  <StandardForm
    class="col-auto subscription-form"
    method={ChangesetService.method.setChangesetSubscription}
    buildRequest={() => ({
      id: changesetId,
      isSubscribed: !isSubscribed.value,
    })}
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

const CommentForm = ({
  changesetId,
  onSuccess,
}: {
  changesetId: bigint
  onSuccess: (result: AddChangesetCommentResponseValid) => void
}) => (
  <StandardForm
    class="comment-form mb-2"
    method={ChangesetService.method.addChangesetComment}
    resetOnSuccess
    buildRequest={({ formData }) => ({
      id: changesetId,
      body: formData.get("body") as string,
    })}
    onSuccess={(result) => onSuccess(result)}
  >
    <div class="mb-3">
      <textarea
        class="form-control"
        name="body"
        rows={4}
        maxLength={CHANGESET_COMMENT_BODY_MAX_LENGTH}
        required
      />
    </div>
    <div class="text-end">
      <button
        class="btn btn-primary"
        type="submit"
      >
        {t("action.comment")}
      </button>
    </div>
  </StandardForm>
)

const ChangesetComment = ({
  comment,
}: {
  comment: GetChangesetCommentsResponse_CommentValid
}) => (
  <li class="social-entry">
    <p class="header text-muted">
      <a href={`/user/${comment.user!.displayName}`}>
        <img
          class="avatar"
          src={comment.user!.avatarUrl}
          alt={t("alt.profile_picture")}
          loading="lazy"
        />
        {comment.user!.displayName}
      </a>{" "}
      {t("action.commented")}{" "}
      <Time
        unix={comment.createdAt}
        relativeStyle="long"
      />
    </p>
    <div
      class="body"
      dangerouslySetInnerHTML={{ __html: comment.bodyRich }}
    />
  </li>
)

const ChangesetFooter = ({ data }: { data: ChangesetDataValid }) => {
  const changesetIdStr = data.id.toString()
  return (
    <div class="section text-center">
      {data.user && (
        <div class="mb-2">
          {data.prevChangesetId !== undefined && (
            <>
              <a
                href={`/changeset/${data.prevChangesetId}`}
                rel="prev"
              >
                « {data.prevChangesetId}
              </a>
              <span aria-hidden="true"> · </span>
            </>
          )}
          <a
            href={`/user/${data.user.displayName}`}
            rel="author"
          >
            {data.user.displayName}
          </a>
          {data.nextChangesetId !== undefined && (
            <>
              <span aria-hidden="true"> · </span>
              <a
                href={`/changeset/${data.nextChangesetId}`}
                rel="next"
              >
                {data.nextChangesetId} »
              </a>
            </>
          )}
        </div>
      )}
      <small>
        <a href={`${API_URL}/api/0.6/changeset/${changesetIdStr}`}>
          {t("browse.changeset.changesetxml")}
        </a>
        <span aria-hidden="true"> · </span>
        <a href={`${API_URL}/api/0.6/changeset/${changesetIdStr}/download`}>
          {t("browse.changeset.osmchangexml")}
        </a>
      </small>
    </div>
  )
}

const ChangesetElementRow = ({
  element,
  type,
}: {
  element: Element
  type: ElementType
}) => {
  const idStr = element.id.toString()
  const typeSlug = ElementType[type] as keyof typeof ElementType
  return (
    <ElementsListRow
      href={`/${typeSlug}/${idStr}`}
      icon={element.icon}
      class={element.visible ? "" : "deleted"}
      title={element.name || idStr}
      meta={
        <>
          <span>{getElementTypeLabel(type)}</span>
          {element.name && <span>{`#${idStr}`}</span>}
          <span aria-hidden="true"> · </span>
          <a
            href={`/${typeSlug}/${idStr}/history/${element.version}`}
          >{`v${element.version}`}</a>
        </>
      }
    />
  )
}

const ChangesetSidebar = ({
  map,
  id,
}: {
  map: MaplibreMap
  id: ReadonlySignal<bigint>
}) => {
  const isSubscribed = useSignal(false)
  const preloadedComments = useSignal<GetChangesetCommentsResponseValid | null>(null)

  const { resource, data } = useSidebar(
    useComputed(() => ({ id: id.value })),
    ChangesetService.method.getChangeset,
    (r) => r.changeset,
  )

  // Effect: Sync derived state
  useSignalEffect(() => {
    const r = resource.value
    if (r.tag === "not-found") {
      setPageTitle(t("browse.not_found.title"))
    } else if (r.tag === "ready") {
      const d = r.data
      isSubscribed.value = d.isSubscribed
      setPageTitle(`${t("browse.in_changeset")}: ${d.id}`)
    }
  })

  const refocus = (initial = false) => {
    const d = data.value
    if (!d?.bounds.length) return
    const object: OSMChangeset = {
      type: "changeset",
      id: d.id,
      bounds: d.bounds.map((b) =>
        makeBoundsMinimumSize(map, [b.minLon, b.minLat, b.maxLon, b.maxLat]),
      ),
    }
    focusObjects(map, [object], focusPaint, null, initial ? {} : false)
  }

  // Effect: Map focus
  useDisposeSignalEffect((scope) => {
    if (!data.value?.bounds.length) return

    scope.defer(() => focusObjects(map))
    scope.map(map, "zoomend", () => refocus())
    refocus(true)
  })

  return (
    <SidebarContent
      resource={resource}
      notFound={() =>
        t("browse.not_found.sorry", {
          type: t("browse.in_changeset").toLowerCase(),
          id: id.toString(),
        })
      }
    >
      {(d) => (
        <>
          <div class="section">
            <SidebarHeader class="mb-1">
              <h2 class="sidebar-title">
                {t("browse.in_changeset")}: {d.id}
              </h2>
            </SidebarHeader>

            <ChangesetHeader data={d} />
            <Tags tags={d.tags} />

            {/* Report button */}
            {isLoggedIn && d.user && config.userConfig!.id !== d.user.id && (
              <div class="text-end mt-1 me-1">
                <ReportButton
                  class="btn btn-link btn-sm text-muted p-0"
                  reportType="user"
                  reportTypeId={d.user.id}
                  reportAction="user_changeset"
                  reportActionId={d.id}
                >
                  <i class="bi bi-flag small me-1-5" />
                  {t("report.report_object", {
                    object: t("changeset.count", { count: 1 }),
                  })}
                </ReportButton>
              </div>
            )}

            <div class="mb-4" />

            {/* Discussion section */}
            <div class="row g-1 mb-1">
              <div class="col">
                <h4>{t("browse.changeset.discussion")}</h4>
              </div>
              {isLoggedIn && (
                <SubscriptionForm
                  changesetId={d.id}
                  isSubscribed={isSubscribed}
                />
              )}
            </div>

            {/* Comments pagination */}
            <StandardPagination
              key={d.id}
              method={ChangesetService.method.getChangesetComments}
              request={{ id: d.id }}
              ariaLabel={t("alt.comments_page_navigation")}
              pageOrder="desc"
              responseSignal={preloadedComments}
              small
            >
              {(page) => (
                <ul class="list-unstyled mb-2">
                  {page.comments.map((comment) => (
                    <ChangesetComment comment={comment} />
                  ))}
                </ul>
              )}
            </StandardPagination>

            {/* Comment form or login prompt */}
            {isLoggedIn ? (
              <CommentForm
                changesetId={d.id}
                onSuccess={(result) => {
                  resource.value = { tag: "ready", data: result.changeset }
                  preloadedComments.value = result.comments
                }}
              />
            ) : (
              <div class="text-center mb-2">
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

            {/* Elements sections */}
            <div class="elements mt-4 mb-1">
              {(
                [
                  ["nodes", ElementType.node],
                  ["ways", ElementType.way],
                  ["relations", ElementType.relation],
                ] as const
              ).map(([key, type]) => (
                <ElementsSection
                  key={key}
                  keyFn={(el) => `${key}-${el.id}-${el.version}`}
                  items={d[key]}
                  title={getChangesetElementsTitle(type)}
                  renderRow={(el) => (
                    <ChangesetElementRow
                      element={el}
                      type={type}
                    />
                  )}
                />
              ))}
            </div>
          </div>

          <ChangesetFooter data={d} />
        </>
      )}
    </SidebarContent>
  )
}

export const ChangesetRoute = defineRoute({
  id: "changeset",
  path: ["/changeset/:id", "/changeset/:id/unsubscribe"],
  params: { id: routeParam.positive() },
  Component: ChangesetSidebar,
})
