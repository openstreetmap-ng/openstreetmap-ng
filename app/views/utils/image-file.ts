import { t } from "i18next"

const formatSize = (bytes: number) =>
  bytes >= 1024 * 1024
    ? `${(bytes / (1024 * 1024)).toFixed(1)} MiB`
    : `${Math.ceil(bytes / 1024)} KiB`

/**
 * Validate the selected image file size against a backend limit.
 * Flags a friendly error via native validity and clears the input.
 * Returns true when the selected file is acceptable (or none selected).
 */
export const checkImageFileSize = (
  input: HTMLInputElement,
  maxFileSize: number,
) => {
  const file = input.files?.[0]
  if (!file || file.size <= maxFileSize) {
    input.setCustomValidity("")
    return true
  }

  input.setCustomValidity(
    t("validation.image_file_too_large", { max: formatSize(maxFileSize) }),
  )
  input.reportValidity()
  input.value = ""
  return false
}
