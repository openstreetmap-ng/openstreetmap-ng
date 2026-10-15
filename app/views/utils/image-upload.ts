import { IMAGE_UPLOAD_MAX_SIZE } from "@utils/config"
import { t } from "i18next"

/** Reject oversized images before reading their bytes or sending an RPC request. */
export const formDataImage = async (formData: FormData, name: string) => {
  const file = formData.get(name) as Blob
  if (file.size > IMAGE_UPLOAD_MAX_SIZE) {
    throw new Error(t("validation.image_file_too_big"))
  }
  return new Uint8Array(await file.arrayBuffer())
}
