/** Instantiate the server-rendered form without intercepting native POST. */
export const configureTagEditor = (host: HTMLElement, onDiscard: () => void) => {
  const template = document.getElementById(
    "ElementTagEditorTemplate",
  ) as HTMLTemplateElement
  host.replaceChildren(template.content.cloneNode(true))
  const form = host.querySelector("form")!
  const tagsInput = form.elements.namedItem("tags") as HTMLTextAreaElement
  const versionInput = form.elements.namedItem("version") as HTMLInputElement
  const abort = new AbortController()
  form.action = host.dataset.action!
  versionInput.value = host.dataset.version!
  form.querySelector("[data-discard]")!.addEventListener(
    "click",
    () => {
      form.reset()
      onDiscard()
    },
    { signal: abort.signal },
  )
  return {
    start: () => {
      form.reset()
      versionInput.value = host.dataset.version!
      const tags: Record<string, string> = JSON.parse(host.dataset.tags!)
      tagsInput.value = Object.entries(tags)
        .map(([key, value]) => `${key}=${value}`)
        .join("\n")
      tagsInput.focus()
    },
    dispose: () => {
      abort.abort()
      host.replaceChildren()
    },
  }
}
