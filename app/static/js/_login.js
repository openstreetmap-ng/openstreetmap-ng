import { qsParse } from "./_qs.js"

const refererInputs = document.querySelectorAll(".login-referer")
if (refererInputs.length > 0) {
    // Attach refer from query string and hash
    // TODO: ensure starts with '/'
    const params = qsParse(location.search.substring(1))
    const referer = (params.referer ?? "") + location.hash
    for (const input of refererInputs) input.value = referer
}
