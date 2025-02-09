import { qsParse } from "../_qs"

const body = document.querySelector("body.oauth-fragment-callback-body")
if (body) {
    console.info("Submitting oauth fragment callback form")
    const form = body.querySelector("form.fragment-callback-form")
    const params = qsParse(window.location.hash.substring(1))
    for (const [k, v] of Object.entries(params)) {
        const input = document.createElement("input")
        input.type = "hidden"
        input.name = k
        input.value = v
        form.append(input)
    }
    form.requestSubmit()
}
