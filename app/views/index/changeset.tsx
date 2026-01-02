import {
  getActionSidebar,
  SidebarContent,
  SidebarHeader,
  switchActionSidebar,
  useSidebarFetch,
} from "@index/_action-sidebar"
import { ElementsListRow, ElementsSection, getElementTypeLabel } from "@index/element"
import { API_URL, config, isLoggedIn } from "@lib/config"
import { Time } from "@lib/datetime-inputs"
import { makeBoundsMinimumSize } from "@lib/map/bounds"
import { type FocusLayerPaint, focusObjects } from "@lib/map/layers/focus-layer"
import {
  type ChangesetCommentPage,
  type ChangesetCommentPage_Comment,
  ChangesetCommentPageSchema,
  type ChangesetCommentResult,
  ChangesetCommentResultSchema,
  type ChangesetData,
  ChangesetDataSchema,
  type ChangesetData_Element as Element,
  ElementType,
} from "@lib/proto/shared_pb"
import { ReportButton } from "@lib/report"
import { configureStandardForm } from "@lib/standard-form"
import {
  type PaginationResponse,
  StandardPagination,
  toPaginationResponse,
} from "@lib/standard-pagination"
import { Tags } from "@lib/tags"
import { setPageTitle } from "@lib/title"
import type { OSMChangeset } from "@lib/types"
import {
  type ReadonlySignal,
  type Signal,
  signal,
  useComputed,
  useSignal,
  useSignalEffect,
} from "@preact/signals"
import { t } from "i18next"
import type { Map as MaplibreMap } from "maplibre-gl"
import { render } from "preact"
import { useRef } from "preact/hooks"

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

const ChangesetHeader = ({ data }: { data: ChangesetData }) => {
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
      action={`/api/web/user-subscription/changeset/${changesetId}/${isSubscribed.value ? "unsubscribe" : "subscribe"}`}
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

type CommentResult = {
  result: ChangesetCommentResult
  commentsResponse: PaginationResponse<ChangesetCommentPage>
}

const CommentForm = ({
  changesetId,
  onSuccess,
}: {
  changesetId: bigint
  onSuccess: (result: CommentResult) => void
}) => {
  const formRef = useRef<HTMLFormElement>(null)

  useSignalEffect(() => {
    const disposeForm = configureStandardForm<ChangesetCommentResult>(
      formRef.current,
      (result, headers) => {
        formRef.current!.reset()
        onSuccess({
          result,
          commentsResponse: toPaginationResponse(result.comments!, headers),
        })
      },
      { protobuf: ChangesetCommentResultSchema },
    )
    return () => disposeForm?.()
  })

  return (
    <form
      ref={formRef}
      class="comment-form mb-2"
      method="POST"
      action={`/api/web/changeset/${changesetId}/comment`}
    >
      <div class="mb-3">
        <textarea
          class="form-control"
          name="comment"
          rows={4}
          maxLength={5000}
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
    </form>
  )
}

const ChangesetComment = ({ comment }: { comment: ChangesetCommentPage_Comment }) => {
  return (
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
}

const ChangesetFooter = ({ data }: { data: ChangesetData }) => {
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
                « {data.prevChangesetId.toString()}
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
                {data.nextChangesetId.toString()} »
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
  const typeSlug = ElementType[type] as "node" | "way" | "relation"
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
  sidebar,
}: {
  map: MaplibreMap
  id: ReadonlySignal<string | null>
  sidebar: HTMLElement
}) => {
  const isSubscribed = useSignal(false)
  const preloadedComments = useSignal<PaginationResponse<ChangesetCommentPage> | null>(
    null,
  )

  const url = useComputed(() => (id.value ? `/api/web/changeset/${id.value}` : null))
  const { resource, data } = useSidebarFetch(url, ChangesetDataSchema)

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

  // Effect: Clear preloaded comments on URL change
  useSignalEffect(() => {
    url.value
    preloadedComments.value = null
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
  useSignalEffect(() => {
    if (!data.value?.bounds.length) return

    const onZoom = () => refocus()
    map.on("zoomend", onZoom)
    refocus(true)

    return () => {
      map.off("zoomend", onZoom)
      focusObjects(map)
    }
  })

  // Effect: Sidebar visibility
  useSignalEffect(() => {
    if (id.value) switchActionSidebar(map, sidebar)
  })

  return (
    <SidebarContent
      resource={resource}
      notFound={() =>
        t("browse.not_found.sorry", {
          type: t("browse.in_changeset").toLowerCase(),
          id: id.value!,
        })
      }
    >
      {(d) => (
        <>
          <div class="section">
            <SidebarHeader class="mb-1">
              <h2 class="sidebar-title">
                {t("browse.in_changeset")}: {d.id.toString()}
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
              key={d.id.toString()}
              action={`/api/web/changeset/${d.id}/comments`}
              label={t("alt.comments_page_navigation")}
              small={true}
              pageOrder="desc"
              protobuf={ChangesetCommentPageSchema}
              responseSignal={preloadedComments}
            >
              {(page) => (
                <ul class="list-unstyled mb-2">
                  {page.comments.map((comment) => (
                    <ChangesetComment
                      comment={comment}
                      key={comment.createdAt}
                    />
                  ))}
                </ul>
              )}
            </StandardPagination>

            {/* Comment form or login prompt */}
            {isLoggedIn ? (
              <CommentForm
                changesetId={d.id}
                onSuccess={({ result, commentsResponse }) => {
                  resource.value = { tag: "ready", data: result.changeset! }
                  preloadedComments.value = commentsResponse
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
                  items={d[key]}
                  title={getChangesetElementsTitle(type)}
                  renderRow={(el) => (
                    <ChangesetElementRow
                      element={el}
                      type={type}
                    />
                  )}
                  keyFn={(el) => `${key}-${el.id}-${el.version}`}
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

export const getChangesetController = (map: MaplibreMap) => {
  const sidebar = getActionSidebar("changeset")
  const id = signal<string | null>(null)

  render(
    <ChangesetSidebar
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
