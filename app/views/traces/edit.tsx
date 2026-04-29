import {
  TRACE_DESCRIPTION_MAX_LENGTH,
  TRACE_NAME_MAX_LENGTH,
  TRACE_TAG_MAX_LENGTH,
  TRACE_TAGS_LIMIT,
} from "@lib/config"
import { MultiInput } from "@lib/multi-input"
import { mountProtoPage } from "@lib/proto-page"
import { EditPageSchema, Service, Visibility } from "@lib/proto/trace_pb"
import { StandardForm } from "@lib/standard-form"
import { throwAbortError } from "@lib/utils"
import { t } from "i18next"
import { MapPreview } from "./_map-preview"

export const MetadataFields = ({
  description = "",
  tags = [],
  visibility,
}: {
  description?: string
  tags?: readonly string[]
  visibility: Visibility
}) => (
  <>
    <label class="form-label d-block mb-3">
      <span class="required">{t("notes.show.description")}</span>
      <input
        type="text"
        class="form-control mt-2"
        name="description"
        defaultValue={description}
        maxLength={TRACE_DESCRIPTION_MAX_LENGTH}
        required
      />
    </label>

    <label class="form-label d-block mb-3">
      {t("browse.tag_details.tags")}
      <div class="mt-2">
        <MultiInput
          name="tags"
          placeholder={t("activerecord.help.trace.tagstring")}
          defaultValue={tags.join(", ")}
          maxItems={[
            TRACE_TAGS_LIMIT,
            t("validation.you_can_add_at_most_count_tags", {
              count: TRACE_TAGS_LIMIT,
            }),
          ]}
          maxItemLength={TRACE_TAG_MAX_LENGTH}
        />
      </div>
    </label>

    <label class="form-label">
      <span class="required">{t("activerecord.attributes.trace.visibility")}</span>
      <span class="small">
        {" — "}
        <a
          class="link-primary"
          href="https://wiki.openstreetmap.org/wiki/Visibility_of_GPS_traces"
          target="_blank"
          rel="help noreferrer"
        >
          {t("traces.edit.visibility_help")}
        </a>
      </span>
    </label>

    <div class="ms-1">
      <div class="form-check mb-3">
        {[
          { value: Visibility.private, label: t("traces.visibility.private") },
          { value: Visibility.trackable, label: t("traces.visibility.trackable") },
          { value: Visibility.public, label: t("traces.visibility.public") },
          {
            value: Visibility.identifiable,
            label: t("traces.visibility.identifiable"),
          },
        ].map(({ value, label }) => (
          <label class="form-check-label w-100 mb-2">
            <input
              class="form-check-input"
              type="radio"
              name="visibility"
              value={value}
              defaultChecked={visibility === value}
            />
            {label}
          </label>
        ))}
      </div>
    </div>
  </>
)

mountProtoPage(EditPageSchema, ({ trace }) => {
  const { metadata } = trace

  return (
    <>
      <div class="content-header">
        <div class="col-lg-10 offset-lg-1 col-xl-8 offset-xl-2 col-xxl-6 offset-xxl-3">
          <h1>{t("traces.edit.title", { name: metadata.name })}</h1>
        </div>
      </div>
      <div class="content-body">
        <div class="col-lg-10 offset-lg-1 col-xl-8 offset-xl-2 col-xxl-6 offset-xxl-3">
          <MapPreview
            line={trace.line}
            small
            class="mb-3"
          />

          <StandardForm
            method={Service.method.update}
            buildRequest={({ formData }) => ({
              id: trace.id,
              metadata: {
                name: formData.get("name") as string,
                description: formData.get("description") as string,
                tags: formData.getAll("tags") as string[],
                visibility: Number(formData.get("visibility")) as Visibility,
              },
            })}
            onSuccess={(_, ctx) => ctx.redirect(`/trace/${trace.id}`)}
          >
            <label class="form-label d-block mb-3">
              <span class="required">{t("oauth2_applications.index.name")}</span>
              <input
                type="text"
                class="form-control mt-2"
                name="name"
                defaultValue={metadata.name}
                maxLength={TRACE_NAME_MAX_LENGTH}
                required
              />
            </label>

            <MetadataFields
              description={metadata.description}
              tags={metadata.tags}
              visibility={metadata.visibility}
            />

            <div class="d-flex justify-content-between">
              <a
                class="btn btn-secondary px-3"
                href={`/trace/${trace.id}`}
              >
                {t("action.cancel")}
              </a>
              <button
                class="btn btn-primary px-3"
                type="submit"
              >
                {t("action.save_changes")}
              </button>
            </div>
          </StandardForm>

          <hr class="my-4" />

          <h3 class="mb-3">{t("settings.danger_zone")}</h3>
          <StandardForm
            method={Service.method.delete}
            buildRequest={() => {
              if (!confirm(t("trace.delete_confirmation"))) throwAbortError()
              return { id: trace.id }
            }}
            onSuccess={(_, ctx) =>
              ctx.redirect(`/user/${trace.user.displayName}/traces`)
            }
          >
            <button
              class="btn btn-outline-danger"
              type="submit"
            >
              {t("trace.delete_trace")}
            </button>
          </StandardForm>
        </div>
      </div>
    </>
  )
})
