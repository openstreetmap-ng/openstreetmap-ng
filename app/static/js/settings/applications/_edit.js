import { t } from "i18next"
import { configureStandardForm } from "../../_standard-form.js"

const body = document.querySelector("body.settings-application-edit-body")
if (body) {
    const editForm = body.querySelector("form.edit-form")
    const resetClientSecretButton = body.querySelector("button.reset-client-secret")
    const resetClientSecretForm = body.querySelector("form.reset-client-secret-form")
    const deleteForm = body.querySelector("form.delete-form")
    const deleteButton = deleteForm.querySelector("button[type=submit]")
    const copyGroups = body.querySelectorAll(".copy-group")

    const onEditFormSuccess = () => {
        window.location.reload()
    }

    const onResetClientSecretClick = () => {
        if (confirm(t("settings.new_client_secret_question"))) {
            resetClientSecretForm.requestSubmit()
        }
    }

    const onResetClientSecretFormSuccess = ({ client_secret }) => {
        console.debug("onResetClientSecretFormSuccess")
        const input = resetClientSecretButton.parentElement.querySelector("input")
        input.value = client_secret
        input.dispatchEvent(new Event("change"))
    }

    // On button click, request confirmation
    const onDeleteClick = (event) => {
        if (!confirm(t("settings.delete_this_application_question"))) {
            event.preventDefault()
        }
    }

    // On success callback, navigate to my traces
    const onDeleteFormSuccess = ({ redirect_url }) => {
        console.debug("onFormSuccess", redirect_url)
        window.location = redirect_url
    }

    // On copy group input focus, select all text
    const onCopyInputFocus = (e) => {
        e.target.select()
    }

    // On copy group button click, copy input and change tooltip text
    const onCopyButtonClick = async (e) => {
        const copyButton = e.target.closest("button")
        const copyIcon = copyButton.querySelector("i")
        const copyGroup = copyButton.closest(".copy-group")
        const copyInput = copyGroup.querySelector(".form-control")

        // Visual feedback
        copyInput.select()

        try {
            // Write to clipboard
            const text = copyInput.value
            await navigator.clipboard.writeText(text)
            console.debug("Copied to clipboard", text)
        } catch (error) {
            console.error("Failed to write to clipboard", error)
            alert(error.message)
            return
        }

        if (copyIcon.timeout) clearTimeout(copyIcon.timeout)

        copyIcon.classList.remove("bi-copy")
        copyIcon.classList.add("bi-check2")

        copyIcon.timeout = setTimeout(() => {
            copyIcon.classList.remove("bi-check2")
            copyIcon.classList.add("bi-copy")
        }, 1500)
    }

    configureStandardForm(editForm, onEditFormSuccess)
    resetClientSecretButton.addEventListener("click", onResetClientSecretClick)
    configureStandardForm(resetClientSecretForm, onResetClientSecretFormSuccess)
    deleteButton.addEventListener("click", onDeleteClick)
    configureStandardForm(deleteForm, onDeleteFormSuccess)
    for (const copyGroup of copyGroups) {
        const copyInput = copyGroup.querySelector(".form-control")
        copyInput.addEventListener("focus", onCopyInputFocus)
        const copyButton = copyGroup.querySelector(".bi-copy").parentElement
        copyButton.addEventListener("click", onCopyButtonClick)
    }
}
