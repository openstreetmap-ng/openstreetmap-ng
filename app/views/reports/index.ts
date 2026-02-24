import { queryParam } from "@lib/codecs"
import { mount } from "@lib/mount"
import { defineQueryContract } from "@lib/query-contract"
import { configureStandardPagination } from "@lib/standard-pagination"

const FILTER_QUERY = defineQueryContract({ status: queryParam.text() })

mount("reports-body", (body) => {
  const reportStatusFilter = body.querySelector("select#reportStatusFilter")!
  reportStatusFilter.addEventListener("change", () => {
    const status = reportStatusFilter.value
    console.debug("ReportsIndex: Status filter changed", status)
    window.location.search = FILTER_QUERY.encode({ status })
  })

  configureStandardPagination(body.querySelector("div.reports-pagination"))
})
