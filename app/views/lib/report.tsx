import { REPORT_COMMENT_BODY_MAX_LENGTH } from "@lib/config"
import { configureStandardForm } from "@lib/standard-form"
import { memoize } from "@std/cache/memoize"
import { Modal } from "bootstrap"
import { t } from "i18next"
import type { HTMLAttributes, MouseEventHandler, RefObject } from "preact"
import { createRef, render } from "preact"

type ReportType = "anonymous_note" | "user"

type ReportAction =
  | "comment"
  | "close"
  | "reopen"
  | "generic"
  | "user_account"
  | "user_changeset"
  | "user_diary"
  | "user_message"
  | "user_note"
  | "user_oauth2_application"
  | "user_profile"
  | "user_trace"

interface ReportData {
  type: ReportType
  typeId: bigint
  action: ReportAction
  actionId: bigint | undefined
}

const ReportModal = ({
  formRef,
  modalBodyRef,
}: {
  formRef: RefObject<HTMLFormElement>
  modalBodyRef: RefObject<HTMLDivElement>
}) => (
  <div
    id="reportModal"
    class="modal fade"
    tabIndex={-1}
    aria-hidden="true"
  >
    <div class="modal-dialog modal-dialog-centered">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title">{t("report.report_content")}</h5>
          <button
            class="btn-close"
            type="button"
            data-bs-dismiss="modal"
            aria-label={t("javascripts.close")}
          />
        </div>

        <form
          method="POST"
          action="/api/web/reports"
          ref={formRef}
        >
          <div
            class="modal-body"
            ref={modalBodyRef}
          >
            <input
              type="hidden"
              name="type"
            />
            <input
              type="hidden"
              name="type_id"
            />
            <input
              type="hidden"
              name="action"
            />
            <input
              type="hidden"
              name="action_id"
            />

            <label class="form-label d-block mb-3">
              <span class="required">{t("report.category")}</span>
              <select
                name="category"
                class="form-select mt-2"
                required
              >
                <option value="">{t("report.select_a_category")}</option>
                <option value="vandalism">{t("report.category_vandalism")}</option>
                <option value="spam">{t("report.category_spam")}</option>
                <option value="harassment">{t("report.category_harassment")}</option>
                <option value="privacy">{t("report.category_privacy_issue")}</option>
                <option value="other">{t("report.category_o_ther")}</option>
              </select>
            </label>

            <label class="form-label d-block">
              <span class="required">{t("report.description")}</span>
              <textarea
                name="body"
                class="form-control mt-2"
                rows={4}
                placeholder={t("report.please_describe_the_issue")}
                maxLength={REPORT_COMMENT_BODY_MAX_LENGTH}
                required
              />
            </label>
            <div class="form-text">
              {t("report.provide_details_to_help_us_understand_the_problem")}
            </div>
          </div>

          <div class="modal-footer">
            <button
              type="button"
              class="btn btn-secondary"
              data-bs-dismiss="modal"
            >
              {t("javascripts.close")}
            </button>
            <button
              type="submit"
              class="btn btn-primary"
            >
              <i class="bi bi-flag me-2" />
              {t("report.submit_report")}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
)

const getModal = memoize(() => {
  const formRef = createRef<HTMLFormElement>()
  const modalBodyRef = createRef<HTMLDivElement>()

  const root = document.createElement("div")
  render(
    <ReportModal
      formRef={formRef}
      modalBodyRef={modalBodyRef}
    />,
    root,
  )
  document.body.append(root)

  const modal = root.firstElementChild as HTMLDivElement
  const form = formRef.current!
  const modalBody = modalBodyRef.current!
  const categorySelect = form.elements.namedItem("category") as HTMLSelectElement

  const instance = Modal.getOrCreateInstance(modal)
  configureStandardForm(
    form,
    () => {
      console.debug("ReportModal: Submitted")
      form.reset()
    },
    {
      removeEmptyFields: true,
      formBody: modalBody,
    },
  )

  return { instance, form, categorySelect }
})

const showReportModal = (data: ReportData) => {
  const refs = getModal()

  const restrict = data.action === "user_account"
  for (const option of refs.categorySelect.options) {
    option.hidden = restrict
      ? !(!option.value || option.value === "privacy" || option.value === "other")
      : false
  }

  const setField = (name: string, value: string) => {
    const input = refs.form.elements.namedItem(name) as HTMLInputElement
    input.value = value
  }
  setField("type", data.type)
  setField("type_id", data.typeId.toString())
  setField("action", data.action)
  setField("action_id", data.actionId?.toString() || "")

  refs.instance.show()
}

export const ReportButton = ({
  reportType,
  reportTypeId,
  reportAction,
  reportActionId,
  onClick,
  children,
  ...props
}: HTMLAttributes<HTMLButtonElement> & {
  reportType: ReportType
  reportTypeId: bigint
  reportAction: ReportAction
  reportActionId?: bigint
}) => {
  const handleClick: MouseEventHandler<HTMLButtonElement> = (event) => {
    onClick?.(event)
    if (event.defaultPrevented) return
    event.preventDefault()
    showReportModal({
      type: reportType,
      typeId: reportTypeId,
      action: reportAction,
      actionId: reportActionId,
    })
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      {...props}
    >
      {children}
    </button>
  )
}

// Configure report buttons in dynamic content
export const configureReportButtons = (searchElement: Element) => {
  for (const button of searchElement.querySelectorAll("button[data-report-type]")) {
    button.addEventListener("click", (event) => {
      event.preventDefault()
      const { reportType, reportTypeId, reportAction, reportActionId } = button.dataset
      showReportModal({
        type: reportType as ReportType,
        typeId: BigInt(reportTypeId!),
        action: reportAction as ReportAction,
        actionId: reportActionId ? BigInt(reportActionId) : undefined,
      })
    })
    button.removeAttribute("data-report-type")
  }
}

configureReportButtons(document.body)
