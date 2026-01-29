import { preferredEditorStorage } from "@lib/local-storage"

if (window.location.pathname === "/edit") {
  const url = new URL(window.location.href)
  if (!url.searchParams.has("editor")) {
    url.searchParams.set("editor", preferredEditorStorage.value)
    window.location.replace(url.pathname + url.search + url.hash)
  }
}
