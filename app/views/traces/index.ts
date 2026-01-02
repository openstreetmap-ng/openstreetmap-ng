import { mount } from "@lib/mount"
import { configureStandardPagination } from "@lib/standard-pagination"
import { configureTracesList } from "./_list"

mount("traces-index-body", (body) => {
  const tracesPagination = body.querySelector("div.traces-pagination")!
  configureStandardPagination(tracesPagination, {
    loadCallback: configureTracesList,
  })
})
