import { StandardForm } from "@components/standard-form"
import type { Signal } from "@preact/signals"
import { Service } from "@proto/settings_pb"
import { USER_DESCRIPTION_MAX_LENGTH } from "@utils/config"
import { Modal } from "bootstrap"
import { t } from "i18next"
import { useId, useRef } from "preact/hooks"
import { RichTextControl } from "../../rich-text/control"

export const PROFILE_DESCRIPTION_MODAL_ID = "ProfileDescriptionModal"

export const DescriptionModal = ({
  description,
  descriptionRich,
}: {
  description: Signal<string | undefined>
  descriptionRich: Signal<string>
}) => {
  const labelId = useId()
  const modalRef = useRef<HTMLDivElement>(null)

  return (
    <div
      class="modal fade"
      id={PROFILE_DESCRIPTION_MODAL_ID}
      tabIndex={-1}
      aria-labelledby={labelId}
      aria-hidden="true"
      ref={modalRef}
    >
      <div class="modal-dialog modal-lg">
        <StandardForm
          class="description-form modal-content"
          method={Service.method.updateDescription}
          buildRequest={({ formData }) => ({
            description: formData.get("description") as string,
          })}
          onSuccess={(resp) => {
            description.value = resp.description
            descriptionRich.value = resp.descriptionRich
            Modal.getOrCreateInstance(modalRef.current!).hide()
          }}
        >
          <div class="modal-header">
            <h5
              class="modal-title"
              id={labelId}
            >
              {t("user.edit_description")}
            </h5>
            <button
              class="btn-close"
              aria-label={t("javascripts.close")}
              type="button"
              data-bs-dismiss="modal"
            />
          </div>
          <div class="modal-body">
            <RichTextControl
              name="description"
              value={description.value ?? ""}
              maxLength={USER_DESCRIPTION_MAX_LENGTH}
            />
          </div>
          <div class="modal-footer d-flex justify-content-between">
            <div>
              <p class="form-text m-0">
                {t("user.your_profile_description_is_displayed_publicly")}
              </p>
            </div>
            <div>
              <button
                class="btn btn-secondary me-2"
                type="button"
                data-bs-dismiss="modal"
              >
                {t("javascripts.close")}
              </button>
              <button
                class="btn btn-primary"
                type="submit"
              >
                {t("action.save_changes")}
              </button>
            </div>
          </div>
        </StandardForm>
      </div>
    </div>
  )
}
