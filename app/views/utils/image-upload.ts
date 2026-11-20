import { REQUEST_BODY_MAX_SIZE } from "@utils/config"
import { t } from "i18next"

export const imageFormDataBytes = async (
  formData: FormData,
  name: string,
  input: HTMLInputElement,
) => {
  const file = formData.get(name) as File
  if (file.size > REQUEST_BODY_MAX_SIZE) {
    input.value = ""
    throw new Error(t("validation.image_file_too_big"))
  }
  return new Uint8Array(await file.arrayBuffer())
}
