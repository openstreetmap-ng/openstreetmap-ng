import { mount } from "@lib/mount"
import { qsParse } from "@lib/qs"

mount("oauth-fragment-callback-body", (body) => {
    console.info("Submitting oauth fragment callback form")
    const form = body.querySelector("form.fragment-callback-form")!
    const params = qsParse(window.location.hash)
    for (const [k, v] of Object.entries(params)) {
        const input = document.createElement("input")
        input.type = "hidden"
        input.name = k
        input.value = v
        form.append(input)
    }
    form.requestSubmit()
})
