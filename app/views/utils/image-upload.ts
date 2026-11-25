import { t } from "i18next"

export const AVATAR_MAX_PIXELS = 384 * 384
export const BACKGROUND_MAX_PIXELS = 4096 * 512

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

export const validateImageUpload = async (
  formData: FormData,
  name: string,
  maxPixels: number,
) => {
  const value = formData.get(name)
  if (!(value instanceof File) || value.size === 0) return

  const { height, width } = await loadImageDimensions(value)
  if (height > 0 && width > 0 && height * width > maxPixels) {
    throw new Error(t("validation.image_too_large"))
  }
}
