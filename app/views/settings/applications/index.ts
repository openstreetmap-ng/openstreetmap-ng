import { Collapse } from "bootstrap"
import { mount } from "../../lib/mount"
import { qsEncode, qsParse } from "../../lib/qs"
import { configureStandardForm } from "../../lib/standard-form"

mount("settings-applications-body", (body) => {
    // Fixup links in buttons
    const accordionButtons = body.querySelectorAll("button.accordion-button")
    for (const button of accordionButtons) {
        const collapse = document.querySelector(button.dataset.bsTarget)
        const collapseInstance = Collapse.getOrCreateInstance(collapse, {
            toggle: false,
        })
        // @ts-expect-error
        collapseInstance._triggerArray.push(button)

        // On accordion button click, toggle the collapse if target is not a link
        button.addEventListener("click", ({ target }: Event) => {
            const tagName = (target as HTMLElement).tagName
            if (tagName === "A") return
            collapseInstance.toggle()
        })
    }

    // settings/applications + settings/applications/tokens
    const revokeApplicationForms = body.querySelectorAll("form.revoke-application-form")
    for (const form of revokeApplicationForms) {
        configureStandardForm(form, () => {
            console.debug("onRevokeApplicationFormSuccess")
            form.closest("li").remove()
        })
    }

    // settings/applications/admin
    const createApplicationButton = body.querySelector("button.create-application-btn")
    if (createApplicationButton) {
        const createApplicationForm = body.querySelector("form.create-application-form")

        // On create new application button click, show the form and focus the name input
        createApplicationButton.addEventListener("click", () => {
            console.debug("onCreateNewApplicationClick")
            createApplicationButton.classList.add("d-none")
            createApplicationForm.classList.remove("d-none")
            const nameInput = createApplicationForm.querySelector("input[name=name]")
            nameInput.focus()
        })

        configureStandardForm(createApplicationForm, ({ redirect_url }) => {
            console.debug("onCreateApplicationFormSuccess", redirect_url)
            window.location.href = redirect_url
        })
    }

    // settings/applications/tokens
    const createTokenForm = body.querySelector("form.create-token-form")
    if (createTokenForm) {
        configureStandardForm(createTokenForm, ({ token_id }) => {
            // On success callback, reload the page
            console.debug("onCreateTokenFormSuccess", token_id)
            const searchParams = qsParse(window.location.search)
            searchParams.expand = token_id
            window.location.href = `${window.location.pathname}?${qsEncode(searchParams)}${window.location.hash}`
        })
    }
})
