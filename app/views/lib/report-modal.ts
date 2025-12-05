import { Modal } from "bootstrap"
import { configureStandardForm } from "./standard-form"

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

export interface ReportData {
    type: ReportType
    typeId: number
    action: ReportAction
    actionId?: string
}

const modalElement = document.getElementById("reportModal")
const modalInstance = modalElement ? new Modal(modalElement) : null
const formElement = modalElement?.querySelector("form")

export const configureReportButton = (
    button?: HTMLButtonElement,
    data?: ReportData,
) => {
    if (!button) return

    if (!data)
        data = {
            type: button.dataset.reportType as ReportType,
            typeId: Number.parseInt(button.dataset.reportTypeId, 10),
            action: button.dataset.reportAction as ReportAction,
            actionId: button.dataset.reportActionId,
        }

    button.addEventListener("click", (e) => {
        e.preventDefault()
        showReportModal(data)
    })
}

export const showReportModal = (data: ReportData) => {
    const typeInput = formElement.querySelector("input[name=type]")
    const typeIdInput = formElement.querySelector("input[name=type_id]")
    const actionInput = formElement.querySelector("input[name=action]")
    const actionIdInput = formElement.querySelector("input[name=action_id]")
    const categorySelect = formElement.querySelector("select[name=category]")

    // Special handling for certain actions - limit categories
    if (data.action === "user_account") {
        for (const option of categorySelect.options) {
            option.hidden = !(
                !option.value ||
                option.value === "privacy" ||
                option.value === "other"
            )
        }
    } else {
        for (const option of categorySelect.options) {
            option.hidden = false
        }
    }

    typeInput.value = data.type
    typeIdInput.value = data.typeId.toString()
    actionInput.value = data.action
    actionIdInput.value = data.actionId ?? ""

    modalInstance.show()
}

// Configure report buttons in dynamic content
export const configureReportButtonsLazy = (searchElement: Element): void =>
    queueMicrotask(() => {
        let counter = 0
        for (const button of searchElement.querySelectorAll(
            "button[data-report-type]",
        )) {
            configureReportButton(button)
            button.removeAttribute("data-report-type")
            button.removeAttribute("data-report-type-id")
            button.removeAttribute("data-report-action")
            button.removeAttribute("data-report-action-id")
            counter++
        }
        if (counter) {
            console.debug("Configured", counter, "report buttons")
        }
    })

if (modalElement) {
    configureStandardForm(
        formElement,
        () => {
            console.debug("Report submitted successfully")
            formElement.reset()
        },
        {
            removeEmptyFields: true,
            formBody: formElement.querySelector(".modal-body"),
        },
    )

    configureReportButtonsLazy(document.body)
}
