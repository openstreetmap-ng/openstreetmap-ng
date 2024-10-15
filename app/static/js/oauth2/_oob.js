import { initializeCopyGroups } from "../_copy-group.js"

const body = document.querySelector("body.oauth-oob-body")
if (body) {
    const copyGroups = body.querySelectorAll(".copy-group")
    initializeCopyGroups(copyGroups)
}
