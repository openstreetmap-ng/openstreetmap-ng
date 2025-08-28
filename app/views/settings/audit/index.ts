import { configureStandardPagination } from "../../lib/standard-pagination"

const body = document.querySelector("body.settings-audit-body")
if (body) {
    configureStandardPagination(body, { reverse: false })
}
