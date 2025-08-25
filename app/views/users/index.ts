import { configureStandardPagination } from "../lib/standard-pagination"

const body = document.querySelector("body.users-body")
if (body) {
    configureStandardPagination(body, { reverse: false })
}
