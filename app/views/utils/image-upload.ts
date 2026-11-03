/** Check image input limits before reading the upload into a request buffer. */
export const imageUploadBytes = async (
  formData: FormData,
  name: string,
  {
    input,
    maxBytes,
    maxPixels,
    fileError,
    dimensionsError,
    signal,
  }: {
    input: HTMLInputElement
    maxBytes: number
    maxPixels: number | null
    fileError: string
    dimensionsError: string
    signal: AbortSignal
  },
) => {
  const file = formData.get(name) as File | null
  if (!file?.size) return new Uint8Array()

  try {
    signal.throwIfAborted()
    // These avatar/background requests contain one bytes field: tag + length + data.
    let encodedSize = file.size + 1
    for (let length = file.size; length >= 1; length = Math.floor(length / 128))
      encodedSize++
    if (encodedSize > maxBytes) throw new Error(fileError)

    if (maxPixels !== null) {
      const image = new Image(),
        url = URL.createObjectURL(file)
      let onAbort: (() => void) | undefined, onLoad: (() => void) | undefined
      try {
        await new Promise<void>((resolve, reject) => {
          onLoad = () => resolve()
          image.addEventListener("load", onLoad, { once: true })
          // Pillow supports formats that browsers cannot decode. Let it decide.
          image.addEventListener("error", onLoad, { once: true })
          onAbort = () => reject(signal.reason)
          signal.addEventListener("abort", onAbort, { once: true })
          image.src = url
        })
        signal.throwIfAborted()
        if (image.naturalWidth * image.naturalHeight > maxPixels)
          throw new Error(dimensionsError)
      } finally {
        if (onAbort) signal.removeEventListener("abort", onAbort)
        if (onLoad) {
          image.removeEventListener("load", onLoad)
          image.removeEventListener("error", onLoad)
        }
        image.src = ""
        URL.revokeObjectURL(url)
      }
    }

    signal.throwIfAborted()
    const buffer = await file.arrayBuffer()
    signal.throwIfAborted()
    return new Uint8Array(buffer)
  } catch (error) {
    // A failed upload must allow selecting the same file again.
    if (!signal.aborted) input.value = ""
    throw error
  }
}
