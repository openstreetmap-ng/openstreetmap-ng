import { REPORT_COMMENT_BODY_MAX_LENGTH } from "@lib/config"
import { configureStandardForm } from "@lib/standard-form"
import { computed, signal, useSignalEffect } from "@preact/signals"
import { memoize } from "@std/cache/memoize"
import { Modal } from "bootstrap"
import { t } from "i18next"
import type { HTMLAttributes, TargetedMouseEvent } from "preact"
import { render } from "preact"
import { useId, useRef } from "preact/hooks"

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

const reportData = signal<ReportData | null>(null)
const isSelfReport = computed(() => reportData.value?.action === "user_account")

const ReportModal = () => {
  const modalRef = useRef<HTMLDivElement>(null)
  const formRef = useRef<HTMLFormElement>(null)
  const modalBodyRef = useRef<HTMLDivElement>(null)
  const categoryId = useId()
  const bodyId = useId()
  const bodyHelpId = useId()

  // Effect: Handle bootstrap modal instance
  useSignalEffect(() => {
    const { type, typeId, action, actionId } = reportData.value!

    Modal.getOrCreateInstance(modalRef.current!).show()

    return configureStandardForm(
      formRef.current!,
      () => {
        console.debug("ReportModal: Submitted")
        formRef.current!.reset()
      },
      {
        removeEmptyFields: true,
        formBody: modalBodyRef.current!,
        validationCallback: (formData) => {
          formData.set("type", type)
          formData.set("type_id", typeId.toString())
          formData.set("action", action)
          if (actionId) formData.set("action_id", actionId.toString())
          return null
        },
      },
    )
  })

  return (
    <div
      class="modal fade"
      tabIndex={-1}
      aria-hidden="true"
      ref={modalRef}
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
              <label
                class="form-label required"
                for={categoryId}
              >
                {t("report.category")}
              </label>
              <select
                id={categoryId}
                name="category"
                class="form-select mb-3"
                required
              >
                <option value="">{t("report.select_a_category")}</option>
                {!isSelfReport.value && (
                  <>
                    <option value="vandalism">{t("report.category_vandalism")}</option>
                    <option value="spam">{t("report.category_spam")}</option>
                    <option value="harassment">
                      {t("report.category_harassment")}
                    </option>
                  </>
                )}
                <option value="privacy">{t("report.category_privacy_issue")}</option>
                <option value="other">{t("report.category_o_ther")}</option>
              </select>

              <label
                class="form-label required"
                for={bodyId}
              >
                {t("report.description")}
              </label>
              <textarea
                id={bodyId}
                name="body"
                class="form-control mb-2"
                rows={4}
                placeholder={t("report.please_describe_the_issue")}
                maxLength={REPORT_COMMENT_BODY_MAX_LENGTH}
                aria-describedby={bodyHelpId}
                required
              />
              <div
                id={bodyHelpId}
                class="form-text"
              >
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
}

const mountModal = memoize(() => {
  const root = document.createElement("div")
  render(<ReportModal />, root)
  document.body.append(root)
})

const showReportModal = (data: ReportData) => {
  reportData.value = data
  mountModal()
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
  const handleClick = (event: TargetedMouseEvent<HTMLButtonElement>) => {
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
