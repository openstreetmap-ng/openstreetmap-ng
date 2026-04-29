import { config } from "@lib/config"
import { Time } from "@lib/datetime-inputs"
import { mountProtoPage } from "@lib/proto-page"
import { DetailsPageSchema } from "@lib/proto/trace_pb"
import { ReportButton } from "@lib/report"
import { t } from "i18next"
import { MapPreview } from "./_map-preview"
import { SummaryCard } from "./_summary"

mountProtoPage(DetailsPageSchema, ({ trace }) => {
  const currentUser = config.userConfig?.user
  const isOwner = currentUser?.id === trace.user.id

  return (
    <>
      <div class="content-header">
        <div class="col-lg-10 offset-lg-1 col-xl-8 offset-xl-2 col-xxl-6 offset-xxl-3">
          <h1>{t("traces.show.title", { name: trace.metadata.name })}</h1>
        </div>
      </div>
      <div class="content-body">
        <div class="col-lg-10 offset-lg-1 col-xl-8 offset-xl-2 col-xxl-6 offset-xxl-3">
          <MapPreview
            line={trace.line}
            class="mb-3"
          />

          <div class="trace-summary mb-4">
            <div class="row g-2">
              <div class="col">
                <SummaryCard
                  summary={{
                    description: trace.metadata.description,
                    tags: trace.metadata.tags,
                    visibility: trace.metadata.visibility,
                    size: trace.size,
                  }}
                  tagBasePath="/traces"
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
                        unix={trace.createdAt}
                        relativeStyle="long"
                      />
                    </>
                  }
                />
              </div>
              {config.userConfig && (
                <div class="col-auto d-none d-md-block">
                  <div
                    class="btn-group"
                    role="group"
                  >
                    <a
                      class="btn btn-sm btn-link"
                      href={`/edit?gpx=${trace.id}`}
                    >
                      <i class="bi bi-pencil fs-5" />
                      <span>{t("traces.trace.edit_map")}</span>
                    </a>
                  </div>
                </div>
              )}
            </div>
          </div>

          <div class="text-end me-1">
            {isOwner && (
              <a
                class="btn btn-soft me-2"
                href={`/trace/${trace.id}/edit`}
              >
                {t("layouts.edit")}
              </a>
            )}
            <a
              class="btn btn-primary px-3"
              href={`/api/0.6/gpx/${trace.id}/data.gpx`}
            >
              {t("action.download_as")} <b>GPX</b>
            </a>
          </div>

          {currentUser && !isOwner && (
            <div class="text-end mt-2 me-1">
              <ReportButton
                class="btn btn-link btn-sm text-muted p-0"
                reportType="user"
                reportTypeId={trace.user.id}
                reportAction="user_trace"
                reportActionId={trace.id}
              >
                <i class="bi bi-flag small me-1-5" />
                {t("report.report_object", { object: t("trace.count", { count: 1 }) })}
              </ReportButton>
            </div>
          )}
        </div>
      </div>
    </>
  )
})
