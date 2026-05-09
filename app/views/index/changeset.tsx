import { SidebarContent, SidebarHeader, useSidebar } from "@index/_action-sidebar"
import { ElementsListRow, ElementsSection, getElementTypeLabel } from "@index/element"
import { defineRoute } from "@index/router"
import { pathParam } from "@lib/codecs"
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
  addMapLayer,
  emptyFeatureCollection,
  hasMapLayer,
  layersConfig,
  type LayerId,
} from "@lib/map/layers/layers"
import { convertRenderElementsData, renderObjects } from "@lib/map/render-objects"
import {
  type AddCommentResponseValid,
  type DataValid,
  DiffAction,
  type GetDiffResponse_ElementValid,
  Service,
  type Data_Element as Element,
  type GetCommentsResponse_CommentValid,
  type GetCommentsResponseValid,
} from "@lib/proto/changeset_pb"
import { connectErrorToMessage, rpcClient } from "@lib/rpc"
import { ElementType } from "@lib/proto/shared_pb"
import { ReportButton } from "@lib/report"
import { StandardForm } from "@lib/standard-form"
import { PageOrder, StandardPagination } from "@lib/standard-pagination"
import { Tags } from "@lib/tags"
import { setPageTitle } from "@lib/title"
import { showLoginModal } from "../user/login"
import type { OSMDiffAction, OSMChangeset, OSMObject } from "@lib/types"
import {
  type ReadonlySignal,
  type Signal,
  useComputed,
  useSignal,
  useSignalEffect,
} from "@preact/signals"
import { t } from "i18next"
import type {
  ExpressionSpecification,
  GeoJSONSource,
  Map as MaplibreMap,
} from "maplibre-gl"

const focusPaint: FocusLayerPaint = {
  "fill-opacity": 0,
  "line-color": "#f90",
  "line-opacity": 1,
  "line-width": 3,
}

const DIFF_LAYER_ID = "changeset-diff" as LayerId
const diffActionColor: ExpressionSpecification = [
  "match",
  ["get", "diffAction"],
  "create",
  "#22c55e",
  "modify",
  "#f59e0b",
  "delete",
  "#ef4444",
  "#f90",
]

layersConfig.set(DIFF_LAYER_ID, {
  specification: {
    type: "geojson",
    data: emptyFeatureCollection,
  },
  layerTypes: ["fill", "line", "circle"],
  layerOptions: {
    layout: {
      "line-cap": "round",
      "line-join": "round",
    },
    paint: {
      "circle-color": diffActionColor,
      "circle-opacity": 0.9,
      "circle-radius": 7,
      "circle-stroke-color": "#fff",
      "circle-stroke-width": 2,
      "fill-color": diffActionColor,
      "fill-opacity": 0.18,
      "line-color": diffActionColor,
      "line-opacity": 0.95,
      "line-width": 4,
    },
  },
  priority: 139,
})

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
    return (count: string) => t("browse.changeset.node", { count })
  if (type === ElementType.way)
    return (count: string) => t("browse.changeset.way", { count })
  return (count: string) => t("browse.changeset.relation", { count })
}

const getDiffAction = (action: DiffAction): OSMDiffAction => {
  switch (action) {
    case DiffAction.create:
      return "create"
    case DiffAction.modify:
      return "modify"
    case DiffAction.delete:
      return "delete"
  }
  return "modify"
}

const getChangesetDiffObjects = (
  elements: GetDiffResponse_ElementValid[],
): OSMObject[] => {
  const objects: OSMObject[] = []
  for (const element of elements) {
    const diffAction = getDiffAction(element.action)
    for (const object of convertRenderElementsData(element.render)) {
      objects.push({ ...object, diffAction })
    }
  }
  return objects
}

const ChangesetDiffControls = ({
  enabled,
  error,
  pending,
}: {
  enabled: Signal<boolean>
  error: ReadonlySignal<string | null>
  pending: ReadonlySignal<boolean>
}) => (
  <div class="changeset-diff-controls">
    <button
      class={`btn btn-sm ${enabled.value ? "btn-primary" : "btn-soft"}`}
      type="button"
      aria-pressed={enabled.value}
      onClick={() => (enabled.value = !enabled.value)}
    >
      {pending.value ? (
        <span
          class="spinner-border spinner-border-sm me-1"
          aria-hidden="true"
        />
      ) : (
        <i class="bi bi-intersect me-1" />
      )}
      {t("changeset.diff_mode")}
    </button>
    {enabled.value && (
      <div
        class="changeset-diff-legend"
        aria-label={t("changeset.diff_legend")}
      >
        <span class="diff-create">{t("changeset.created")}</span>
        <span class="diff-modify">{t("changeset.modified")}</span>
        <span class="diff-delete">{t("changeset.deleted")}</span>
      </div>
    )}
    {error.value && <div class="form-text text-danger">{error.value}</div>}
  </div>
)

const ChangesetHeader = ({ data }: { data: DataValid }) => {
  const isOpen = !data.closedAt
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
    method={Service.method.updateSubscription}
    buildRequest={() => ({
      id: changesetId,
      isSubscribed: !isSubscribed.value,
    })}
    onSuccess={(_, ctx) => (isSubscribed.value = ctx.request.isSubscribed)}
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
  onSuccess: (result: AddCommentResponseValid) => void
}) => (
  <StandardForm
    class="comment-form mb-2"
    method={Service.method.addComment}
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
  comment: GetCommentsResponse_CommentValid
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

const ChangesetFooter = ({ data }: { data: DataValid }) => {
  const changesetIdStr = data.id.toString()
  return (
    <div class="section text-center">
      {data.user && (
        <div class="mb-2">
          {data.prevChangesetId && (
            <>
              <a
                href={`/changeset/${data.prevChangesetId}`}
                rel="prev"
              >
                « {data.prevChangesetId}
              </a>
              <span
                class="mx-1"
                aria-hidden="true"
              >
                ·
              </span>
            </>
          )}
          <a
            href={`/user/${data.user.displayName}`}
            rel="author"
          >
            {data.user.displayName}
          </a>
          {data.nextChangesetId && (
            <>
              <span
                class="mx-1"
                aria-hidden="true"
              >
                ·
              </span>
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
        <span
          class="mx-1"
          aria-hidden="true"
        >
          ·
        </span>
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
          <span
            class="mx-1"
            aria-hidden="true"
          >
            ·
          </span>
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
  const diffMode = useSignal(false)
  const diffObjects = useSignal<OSMObject[] | null>(null)
  const diffPending = useSignal(false)
  const diffError = useSignal<string | null>(null)
  const diffChangesetId = useSignal<bigint | null>(null)
  const isSubscribed = useSignal(false)
  const preloadedComments = useSignal<GetCommentsResponseValid | null>(null)

  const { resource, data } = useSidebar(
    useComputed(() => ({ id: id.value })),
    Service.method.get,
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
      if (diffChangesetId.peek() !== d.id) {
        diffChangesetId.value = d.id
        diffObjects.value = null
        diffPending.value = false
        diffError.value = null
      }
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
    if (!data.value?.bounds.length || diffMode.value) {
      focusObjects(map)
      return
    }

    scope.defer(() => focusObjects(map))
    scope.map(map, "zoomend", () => refocus())
    refocus(true)
  })

  // Effect: Changeset diff mode
  useDisposeSignalEffect((scope) => {
    const clearDiff = () =>
      map.getSource<GeoJSONSource>(DIFF_LAYER_ID)?.setData(emptyFeatureCollection)
    scope.defer(clearDiff)

    const d = data.value
    if (!diffMode.value || !d) {
      clearDiff()
      diffPending.value = false
      return
    }

    if (!hasMapLayer(map, DIFF_LAYER_ID)) addMapLayer(map, DIFF_LAYER_ID)
    const cachedObjects = diffObjects.value
    if (cachedObjects) {
      map.getSource<GeoJSONSource>(DIFF_LAYER_ID)?.setData(renderObjects(cachedObjects))
      return
    }

    diffPending.value = true
    diffError.value = null
    void rpcClient(Service)
      .getDiff({ id: d.id }, { signal: scope.signal })
      .then((response) => {
        scope.signal.throwIfAborted()
        const objects = getChangesetDiffObjects(response.elements)
        diffObjects.value = objects
        map.getSource<GeoJSONSource>(DIFF_LAYER_ID)?.setData(renderObjects(objects))
      })
      .catch((error: unknown) => {
        if (scope.signal.aborted) return
        console.error("ChangesetDiff: Failed to fetch", error)
        diffError.value = connectErrorToMessage(error)
        clearDiff()
      })
      .finally(() => {
        if (!scope.signal.aborted) diffPending.value = false
      })
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
            <ChangesetDiffControls
              enabled={diffMode}
              error={diffError}
              pending={diffPending}
            />
            <Tags tags={d.tags} />

            {/* Report button */}
            {isLoggedIn && d.user && config.userConfig!.user.id !== d.user.id && (
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
              method={Service.method.getComments}
              request={{ id: d.id }}
              urlKey="page"
              ariaLabel={t("alt.comments_page_navigation")}
              pageOrder={PageOrder.desc}
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
                  onClick={showLoginModal}
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
  params: { id: pathParam.positive() },
  Component: ChangesetSidebar,
})
