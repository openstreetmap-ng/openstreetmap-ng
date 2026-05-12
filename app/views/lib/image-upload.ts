import { t } from "i18next"

const IMAGE_UPLOAD_MAX_MB = 10
const IMAGE_UPLOAD_MAX_BYTES = IMAGE_UPLOAD_MAX_MB * 1024 * 1024

export const imageFormDataBytes = async (formData: FormData, name: string) => {
  const file = formData.get(name)
  if (!(file instanceof Blob)) return new Uint8Array()

  if (file.size > IMAGE_UPLOAD_MAX_BYTES) {
    throw new Error(
      t("validation.image_file_too_big", { size: IMAGE_UPLOAD_MAX_MB }),
    )
  }

  return new Uint8Array(await file.arrayBuffer())
}
