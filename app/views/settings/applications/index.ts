import { mount } from "@lib/mount"
import { IdResponseSchema } from "@lib/proto/shared_pb"
import { qsEncode, qsParse } from "@lib/qs"
import { configureStandardForm } from "@lib/standard-form"
import { Collapse } from "bootstrap"

mount("settings-applications-body", (body) => {
  // Fixup links in buttons
  const accordionButtons = body.querySelectorAll("button.accordion-button")
  for (const button of accordionButtons) {
    const collapse = document.querySelector(button.dataset.bsTarget!)!
    const collapseInstance = new Collapse(collapse, { toggle: false })
    // @ts-expect-error
    collapseInstance._triggerArray.push(button)

    // On accordion button click, toggle the collapse if target is not a link
    button.addEventListener("click", (e) => {
      const tagName = (e.target as HTMLElement).tagName
      if (tagName === "A") return
      collapseInstance.toggle()
    })
  }

  // settings/applications + settings/applications/tokens
  const revokeApplicationForms = body.querySelectorAll("form.revoke-application-form")
  for (const form of revokeApplicationForms) {
    configureStandardForm(form, () => {
      console.debug("Applications: Revoked")
      form.closest("li")!.remove()
    })
  }

  // settings/applications/admin
  const createApplicationButton = body.querySelector("button.create-application-btn")
  if (createApplicationButton) {
    const createApplicationForm = body.querySelector("form.create-application-form")!

    // On create new application button click, show the form and focus the name input
    createApplicationButton.addEventListener("click", () => {
      console.debug("Applications: Create clicked")
      createApplicationButton.classList.add("d-none")
      createApplicationForm.classList.remove("d-none")
      const nameInput = createApplicationForm.querySelector("input[name=name]")!
      nameInput.focus()
    })

    configureStandardForm(createApplicationForm, ({ redirect_url }) => {
      console.debug("Applications: Created", redirect_url)
      window.location.href = redirect_url
    })
  }

  // settings/applications/tokens
  const createTokenForm = body.querySelector("form.create-token-form")
  if (createTokenForm) {
    configureStandardForm(
      createTokenForm,
      (data) => {
        // On success callback, reload the page
        console.debug("Applications: Token created", data.id)
        const searchParams = qsParse(window.location.search)
        searchParams.expand = data.id.toString()
        window.location.search = qsEncode(searchParams)
      },
      { protobuf: IdResponseSchema },
    )
  }
})
