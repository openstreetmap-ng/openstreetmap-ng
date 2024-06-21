const userTermsBody = document.querySelector("body.user-terms-body")
if (userTermsBody) {
    const residenceInputs = userTermsBody.querySelectorAll("input[name=residence]")
    const legalDocuments = userTermsBody.querySelectorAll(".legal-document[data-residence]")

    const onResidenceChange = (e) => {
        const newResidence = e.target.value
        console.debug("onResidenceChange", e.target.value)

        for (const legalDocument of legalDocuments) {
            legalDocument.classList.toggle("d-none", legalDocument.dataset.residence !== newResidence)
        }
    }

    for (const input of residenceInputs) {
        input.addEventListener("change", onResidenceChange)
    }

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

    const onAbortSignupClick = () => userTermsBody.querySelector("form.abort-signup-form").submit()
    const abortSignupButton = userTermsBody.querySelector(".abort-signup-btn")
    abortSignupButton.addEventListener("click", onAbortSignupClick)
}
