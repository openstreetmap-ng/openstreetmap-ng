import { preferredEditorStorage } from "@utils/local-storage"
import { qsEncode, qsParse } from "@utils/query-string"

if (window.location.pathname === "/edit") {
  const params = qsParse(window.location.search)
  if (!params.editor) {
    params.editor = preferredEditorStorage.value
    window.location.replace(`${qsEncode(params)}${window.location.hash}`)
  }
}
