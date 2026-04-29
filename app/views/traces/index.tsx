import { config } from "@lib/config"
import { Time } from "@lib/datetime-inputs"
import { tRich } from "@lib/i18n"
import { mountProtoPage } from "@lib/proto-page"
import {
  type GetPageResponse_EntryValid,
  type IndexPageValid,
  IndexPageSchema,
  Service,
} from "@lib/proto/trace_pb"
import type { UserValid } from "@lib/proto/shared_pb"
import { StandardPagination } from "@lib/standard-pagination"
import { t } from "i18next"
import { SummaryRow } from "./_summary"

const getHeading = (owner: IndexPageValid["owner"], tag: string | undefined) => {
  const heading =
    owner.case === "self"
      ? t("traces.index.my_gps_traces")
      : owner.case === "profile"
        ? t("traces.index.public_traces_from", {
            user: owner.value.displayName,
          })
        : t("traces.index.public_traces")
  return tag ? `${heading} ${t("traces.index.tagged_with", { tags: tag })}` : heading
}

const Nav = ({
  owner,
  profile,
  basePath,
}: {
  owner: IndexPageValid["owner"]["case"]
  profile: UserValid | undefined
  basePath: string
}) => {
  const currentUser = config.userConfig?.user
  const isSelf = owner === "self"
  const isAll = owner === undefined

  return (
    <nav>
      <ul class="nav nav-tabs nav-tabs-md flex-column flex-md-row">
        <li class="nav-item">
          <a
            href="/traces"
            class={`nav-link ${isAll ? "active" : ""}`}
            aria-current={isAll ? "page" : undefined}
          >
            {t("traces.index.all_traces")}
          </a>
        </li>
        {currentUser && (
          <li class="nav-item">
            <a
              href={`/user/${currentUser.displayName}/traces`}
              class={`nav-link ${isSelf ? "active" : ""}`}
              aria-current={isSelf ? "page" : undefined}
            >
              {t("traces.index.my_traces")}
            </a>
          </li>
        )}
        {profile && !isSelf && (
          <li class="nav-item">
            <a
              href={basePath}
              class="nav-link active"
              aria-current="page"
            >
              {t("traces.index.public_traces_from", {
                user: profile.displayName,
              })}
            </a>
          </li>
        )}
        <li class="nav-item ms-auto">
          {currentUser && (
            <a
              class="btn btn-soft"
              href="/trace/upload"
            >
              <i class="bi bi-pin-map me-2" />
              {t("traces.index.upload_trace")}
            </a>
          )}
        </li>
      </ul>
    </nav>
  )
}

const EmptyState = () => (
  <>
    <h3>{t("traces.index.empty_title")}</h3>
    <p>
      {tRich("traces.index.empty_upload_html", {
        upload_link: <a href="/trace/upload">{t("traces.index.upload_new")}</a>,
        wiki_link: (
          <a
            href="https://wiki.openstreetmap.org/wiki/Beginners_Guide_1.2"
            rel="help"
          >
            {t("traces.index.wiki_page")}
          </a>
        ),
      })}
    </p>
  </>
)

const Row = ({
  trace,
  tagBasePath,
}: {
  trace: GetPageResponse_EntryValid
  tagBasePath: string
}) => {
  const traceHref = `/trace/${trace.summary.id}`

  return (
    <SummaryRow
      summary={trace.summary}
      href={traceHref}
      tagBasePath={tagBasePath}
      header={
        <>
          <a href={`/user/${trace.user.displayName}`}>
            <img
              class="avatar"
              src={trace.user.avatarUrl}
              alt={t("alt.profile_picture")}
              loading="lazy"
            />
            {trace.user.displayName}
          </a>{" "}
          {t("action.uploaded")}{" "}
          <Time
            unix={trace.summary.createdAt}
            relativeStyle="long"
          />
        </>
      }
      title={
        <a
          class="stretched-link"
          href={traceHref}
        >
          {trace.name}
        </a>
      }
      sideAction={
        config.userConfig && (
          <div
            class="btn-group"
            role="group"
          >
            <a
              class="btn btn-sm btn-link"
              href={`/edit?gpx=${trace.summary.id}`}
            >
              <i class="bi bi-pencil fs-5" />
              <span>{t("traces.trace.edit_map")}</span>
            </a>
          </div>
        )
      }
    />
  )
}

mountProtoPage(IndexPageSchema, ({ owner, tag }) => {
  const currentUser = config.userConfig?.user
  const profile = owner.case === "profile" ? owner.value : undefined
  const isSelf = owner.case === "self"
  const basePath = isSelf
    ? `/user/${currentUser!.displayName}/traces`
    : profile
      ? `/user/${profile.displayName}/traces`
      : "/traces"

  return (
    <>
      <div class="content-header pb-0">
        <div class="col-lg-10 offset-lg-1 col-xl-8 offset-xl-2 col-xxl-6 offset-xxl-3">
          <div class="row mb-3">
            {profile && (
              <div class="col-auto">
                <a href={`/user/${profile.displayName}`}>
                  <img
                    class="avatar"
                    src={profile.avatarUrl}
                    alt={t("alt.profile_picture")}
                  />
                </a>
              </div>
            )}
            <div class="col">
              <h1>{getHeading(owner, tag)}</h1>
              <p class="mb-0">
                {t("traces.index.description")}
                {tag && (
                  <a
                    class="ms-2"
                    href={basePath}
                  >
                    <i class="bi bi-x me-1" />
                    {t("traces.index.remove_tag_filter")}
                  </a>
                )}
              </p>
            </div>
          </div>

          <Nav
            owner={owner.case}
            profile={profile}
            basePath={basePath}
          />
        </div>
      </div>

      <div class="content-body">
        <div class="col-lg-10 offset-lg-1 col-xl-8 offset-xl-2 col-xxl-6 offset-xxl-3">
          <StandardPagination
            method={Service.method.getPage}
            request={{
              userId: isSelf ? currentUser!.id : profile?.id,
              tag,
            }}
            urlKey="page"
            navTop
            navClassBottom="mb-0"
          >
            {(data) =>
              data.traces.length ? (
                <ul class="traces-list social-list list-unstyled mb-2">
                  {data.traces.map((trace) => (
                    <Row
                      key={trace.summary.id}
                      trace={trace}
                      tagBasePath={basePath}
                    />
                  ))}
                </ul>
              ) : (
                <EmptyState />
              )
            }
          </StandardPagination>
        </div>
      </div>
    </>
  )
})
