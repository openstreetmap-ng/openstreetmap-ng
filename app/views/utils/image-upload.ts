import { t } from "i18next"

/** Match Pillow's default MAX_IMAGE_PIXELS decompression-bomb limit. */
export const IMAGE_UPLOAD_MAX_PIXELS = 89_478_485

const loadImageDimensions = (file: File) =>
  new Promise<{ height: number; width: number }>((resolve, reject) => {
    const url = URL.createObjectURL(file)
    const img = new Image()

    img.onload = () => {
      URL.revokeObjectURL(url)
      resolve({ height: img.naturalHeight, width: img.naturalWidth })
    }
    img.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error(t("validation.image_not_readable")))
    }
    img.src = url
  })

/**
 * Reject oversized or unreadable image uploads before they are sent.
 * Throws an Error whose message is shown by StandardForm feedback.
 */
export const validateImageUpload = async (
  formData: FormData,
  name: string,
  maxPixels: number = IMAGE_UPLOAD_MAX_PIXELS,
) => {
  const value = formData.get(name)
  if (!(value instanceof File) || value.size === 0) return

  const { height, width } = await loadImageDimensions(value)
  if (height > 0 && width > 0 && height * width > maxPixels) {
    throw new Error(t("validation.image_too_large"))
  }
}
