import { t } from "i18next"

const IMAGE_UPLOAD_MAX_BYTES = 10 * 1024 * 1024

export const assertImageUploadSize = (
  formData: FormData,
  fieldName: string,
) => {
  const file = formData.get(fieldName)
  if (!(file instanceof File) || file.size <= IMAGE_UPLOAD_MAX_BYTES) return

  throw new Error(t("validation.image_file_too_big"))
}
