import { qsParse } from "../_qs.js"

const loginBody = document.querySelector("body.login-body")
if (loginBody) {
    const refererInputs = loginBody.querySelectorAll(".login-referer")
    if (refererInputs.length) {
        // Attach refer from query string and hash
        // TODO: ensure starts with '/'
        const params = qsParse(location.search.substring(1))
        const referer = (params.referer ?? "") + location.hash
        for (const input of refererInputs) input.value = referer
    }
}
