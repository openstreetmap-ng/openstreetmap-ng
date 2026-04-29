import { mountProtoPage } from "@lib/proto-page"
import { Service, UploadPageSchema, Visibility } from "@lib/proto/trace_pb"
import { formDataBytes, StandardForm } from "@lib/standard-form"
import { t } from "i18next"
import { MetadataFields } from "./edit"

const TRACE_FILE_ACCEPT =
  ".gpx, application/gpx+xml, application/xml, text/xml, application/octet-stream, application/gzip, application/x-bzip2, application/zip, application/x-tar, application/zstd"

mountProtoPage(UploadPageSchema, () => (
  <>
    <div class="content-header">
      <h1 class="col-lg-10 offset-lg-1 col-xl-8 offset-xl-2 col-xxl-6 offset-xxl-3">
        {t("traces.new.upload_trace")}
      </h1>
    </div>
    <div class="content-body">
      <div class="col-lg-10 offset-lg-1 col-xl-8 offset-xl-2 col-xxl-6 offset-xxl-3">
        <StandardForm
          method={Service.method.upload}
          buildRequest={async ({ formData }) => ({
            file: await formDataBytes(formData, "file"),
            metadata: {
              name: (formData.get("file") as File).name,
              description: formData.get("description") as string,
              tags: formData.getAll("tags") as string[],
              visibility: Number(formData.get("visibility")) as Visibility,
            },
          })}
          onSuccess={({ id }, ctx) => ctx.redirect(`/trace/${id}`)}
        >
          <label class="form-label d-block mb-3">
            <span class="required">{t("activerecord.attributes.trace.gpx_file")}</span>
            <input
              type="file"
              class="form-control mt-2"
              accept={TRACE_FILE_ACCEPT}
              name="file"
              required
            />
          </label>

          <MetadataFields visibility={Visibility.private} />

          <div class="d-flex justify-content-between align-items-center">
            <a
              class="btn btn-secondary px-3"
              href="/traces"
            >
              {t("action.cancel")}
            </a>
            <span>
              <a
                class="btn btn-link me-3"
                href="https://wiki.openstreetmap.org/wiki/Upload_GPS_tracks"
                target="_blank"
                rel="help noreferrer"
              >
                <i class="bi bi-question-circle me-2" />
                {t("layouts.help")}
              </a>
              <button
                class="btn btn-lg btn-primary px-3"
                type="submit"
              >
                <i class="bi bi-cloud-arrow-up-fill me-2" />
                {t("action.submit")}
              </button>
            </span>
          </div>
        </StandardForm>
      </div>
    </div>
  </>
))
