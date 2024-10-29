const body = document.querySelector("body.user-terms-body")
if (body) {
    const residenceInputs = body.querySelectorAll("input[name=residence]")
    const legalDocuments = body.querySelectorAll("div.legal-document[data-residence]")

    /** On residence change, show appropriate legal documents */
    const onResidenceChange = ({ target }: Event) => {
        const newResidence = (target as HTMLInputElement).value
        console.debug("onResidenceChange", newResidence)

        for (const legalDocument of legalDocuments) {
            legalDocument.classList.toggle("d-none", legalDocument.dataset.residence !== newResidence)
        }
    }
    for (const input of residenceInputs) {
        input.addEventListener("change", onResidenceChange)
    }

    /** Auto-detect residence from browser timezone */
    const autoDetectResidence = () => {
        const timezoneInputMap = new Map([...residenceInputs].map((input) => [input.dataset.timezone, input]))
        const timezoneName = Intl.DateTimeFormat().resolvedOptions().timeZone
        const residenceInput = timezoneInputMap.get(timezoneName)
        console.debug("Residence from timezone", timezoneName, residenceInput)

        if (residenceInput) {
            residenceInput.checked = true
            residenceInput.dispatchEvent(new Event("change"))
        }
    }
    autoDetectResidence()

    // Bind abort signup button to the form
    const abortSignupButton = body.querySelector("button.abort-signup-btn")
    abortSignupButton.addEventListener("click", () => {
        const abortSignupForm = body.querySelector("form.abort-signup-form")
        abortSignupForm.requestSubmit()
    })
}
