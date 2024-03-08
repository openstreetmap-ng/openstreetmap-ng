const userTermsBody = document.querySelector("body.user-terms-body")
if (userTermsBody) {
    const residenceInputs = userTermsBody.querySelectorAll("input[name=residence]")
    const legalDocuments = userTermsBody.querySelectorAll("[data-legal-document]")

    const onResidenceChange = (e) => {
        const newResidence = e.target.value
        console.debug("onResidenceChange", e.target.value)

        for (const legalDocument of legalDocuments) {
            const residence = legalDocument.dataset.legalDocument
            legalDocument.classList.toggle("d-none", residence !== newResidence)
        }
    }

    for (const input of residenceInputs) {
        input.addEventListener("change", onResidenceChange)
    }

    const autoDetectResidence = () => {
        const timezoneResidenceMap = new Map([
            ["Europe/Paris", "france"],
            ["Europe/Rome", "italy"],
        ])
        const timezoneName = Intl.DateTimeFormat().resolvedOptions().timeZone
        const residence = timezoneResidenceMap.get(timezoneName)
        console.debug("Residence from timezone", timezoneName, residence)

        if (residence) {
            const residenceInput = userTermsBody.querySelector(`input[name=residence][value=${residence}]`)
            if (!residenceInput) {
                console.error("Residence input not found", residence)
                return
            }

            residenceInput.checked = true
            residenceInput.dispatchEvent(new Event("change"))
        }
    }

    autoDetectResidence()
}
