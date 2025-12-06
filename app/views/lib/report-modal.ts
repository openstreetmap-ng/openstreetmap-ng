import { assert } from "@lib/assert"
import { configureStandardForm } from "@lib/standard-form"
import { Modal } from "bootstrap"

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
    actionId: string | undefined
}

const modalElement = document.getElementById("reportModal")
const modalInstance = modalElement ? new Modal(modalElement) : null
const formElement = modalElement?.querySelector("form")

export const configureReportButton = (
    button: HTMLButtonElement | null,
    data?: ReportData,
) => {
    if (!button) return

    data ??= {
        type: button.dataset.reportType as ReportType,
        typeId: BigInt(button.dataset.reportTypeId!),
        action: button.dataset.reportAction as ReportAction,
        actionId: button.dataset.reportActionId,
    }

    button.addEventListener("click", (e) => {
        e.preventDefault()
        showReportModal(data)
    })
}

const showReportModal = (data: ReportData) => {
    assert(modalInstance)
    assert(formElement)
    const typeInput = formElement.querySelector("input[name=type]")!
    const typeIdInput = formElement.querySelector("input[name=type_id]")!
    const actionInput = formElement.querySelector("input[name=action]")!
    const actionIdInput = formElement.querySelector("input[name=action_id]")!
    const categorySelect = formElement.querySelector("select[name=category]")!

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
export const configureReportButtonsLazy = (searchElement: Element) =>
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

if (modalElement && formElement) {
    configureStandardForm(
        formElement,
        () => {
            console.debug("Report submitted successfully")
            formElement.reset()
        },
        {
            removeEmptyFields: true,
            formBody: formElement.querySelector(".modal-body")!,
        },
    )

    configureReportButtonsLazy(document.body)
}
