import { preferredEditorStorage } from "@lib/local-storage"
import { qsEncode, qsParse } from "@lib/qs"

if (window.location.pathname === "/edit") {
  const params = qsParse(window.location.search)
  if (!params.editor) {
    params.editor = preferredEditorStorage.value
    window.location.replace(`${qsEncode(params)}${window.location.hash}`)
  }
}
