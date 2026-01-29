import { REPORT_COMMENT_BODY_MAX_LENGTH } from "@lib/config"
import {
  CreateReportRequest_Action,
  CreateReportRequest_Category,
  CreateReportRequest_Type,
  ReportService,
} from "@lib/proto/report_pb"
import { StandardForm } from "@lib/standard-form"
import { computed, signal, useSignalEffect } from "@preact/signals"
import { memoize } from "@std/cache/memoize"
import { Modal } from "bootstrap"
import { t } from "i18next"
import type { HTMLAttributes, TargetedMouseEvent } from "preact"
import { render } from "preact"
import { useId, useRef } from "preact/hooks"

type ReportType = keyof typeof CreateReportRequest_Type
type ReportAction = keyof typeof CreateReportRequest_Action
type ReportCategory = keyof typeof CreateReportRequest_Category

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
  const categoryId = useId()
  const bodyId = useId()
  const bodyHelpId = useId()

  // Effect: show modal on open + reset stale state
  useSignalEffect(() => {
    reportData.value

    formRef.current!.dispatchEvent(new CustomEvent("invalidate"))
    formRef.current!.reset()

    Modal.getOrCreateInstance(modalRef.current!).show()
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
              aria-label={t("javascripts.close")}
              data-bs-dismiss="modal"
            />
          </div>

          <StandardForm
            formRef={formRef}
            feedbackRootSelector=".modal-body"
            method={ReportService.method.createReport}
            resetOnSuccess
            buildRequest={({ formData }) => {
              const { type, typeId, action, actionId } = reportData.value!
              return {
                type: CreateReportRequest_Type[type],
                typeId,
                action: CreateReportRequest_Action[action],
                ...(actionId === undefined ? {} : { actionId }),
                category:
                  CreateReportRequest_Category[
                    formData.get("category")!.toString() as ReportCategory
                  ],
                body: formData.get("body")!.toString(),
              }
            }}
          >
            <div class="modal-body">
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
          </StandardForm>
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
