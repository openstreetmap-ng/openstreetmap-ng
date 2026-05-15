import { IMAGE_UPLOAD_MAX_PIXELS } from "@lib/config"
import { t } from "i18next"

type ImageDimensions = {
  width: number
  height: number
}

const IMAGE_HEADER_BYTES = 64 * 1024

const hasBytes = (view: DataView, offset: number, length: number) =>
  offset >= 0 && offset + length <= view.byteLength

const ascii = (view: DataView, offset: number, length: number) =>
  hasBytes(view, offset, length)
    ? String.fromCharCode(
        ...new Uint8Array(view.buffer, view.byteOffset + offset, length),
      )
    : ""

const uint24LE = (view: DataView, offset: number) =>
  view.getUint8(offset) |
  (view.getUint8(offset + 1) << 8) |
  (view.getUint8(offset + 2) << 16)

const parsePngDimensions = (view: DataView): ImageDimensions | null => {
  if (ascii(view, 0, 8) !== "\x89PNG\r\n\x1A\n" || ascii(view, 12, 4) !== "IHDR")
    return null

  return {
    width: view.getUint32(16),
    height: view.getUint32(20),
  }
}

const isJpegStartOfFrame = (marker: number) =>
  marker >= 0xc0 && marker <= 0xcf && ![0xc4, 0xc8, 0xcc].includes(marker)

const parseJpegDimensions = (view: DataView): ImageDimensions | null => {
  if (!hasBytes(view, 0, 2) || view.getUint16(0) !== 0xffd8) return null

  let offset = 2
  while (hasBytes(view, offset, 4)) {
    if (view.getUint8(offset) !== 0xff) return null
    while (hasBytes(view, offset, 1) && view.getUint8(offset) === 0xff) offset++
    if (!hasBytes(view, offset, 1)) return null

    const marker = view.getUint8(offset++)
    if (marker === 0xd9 || marker === 0xda) return null
    if (marker === 0x01 || (marker >= 0xd0 && marker <= 0xd7)) continue
    if (!hasBytes(view, offset, 2)) return null

    const segmentLength = view.getUint16(offset)
    if (segmentLength < 2) throw new Error(t("validation.image_not_readable"))

    if (isJpegStartOfFrame(marker)) {
      if (!hasBytes(view, offset + 2, 5)) return null
      return {
        height: view.getUint16(offset + 3),
        width: view.getUint16(offset + 5),
      }
    }

    offset += segmentLength
  }

  return null
}

const parseGifDimensions = (view: DataView): ImageDimensions | null => {
  const signature = ascii(view, 0, 6)
  if (signature !== "GIF87a" && signature !== "GIF89a") return null

  return {
    width: view.getUint16(6, true),
    height: view.getUint16(8, true),
  }
}

const parseWebpDimensions = (view: DataView): ImageDimensions | null => {
  if (ascii(view, 0, 4) !== "RIFF" || ascii(view, 8, 4) !== "WEBP") return null

  const chunk = ascii(view, 12, 4)
  if (chunk === "VP8X" && hasBytes(view, 24, 6)) {
    return {
      width: uint24LE(view, 24) + 1,
      height: uint24LE(view, 27) + 1,
    }
  }

  if (chunk === "VP8L" && hasBytes(view, 20, 5) && view.getUint8(20) === 0x2f) {
    const b1 = view.getUint8(21)
    const b2 = view.getUint8(22)
    const b3 = view.getUint8(23)
    const b4 = view.getUint8(24)

    return {
      width: 1 + b1 + ((b2 & 0x3f) << 8),
      height: 1 + (b2 >> 6) + (b3 << 2) + ((b4 & 0x0f) << 10),
    }
  }

  if (chunk === "VP8 " && hasBytes(view, 26, 4)) {
    return {
      width: view.getUint16(26, true) & 0x3fff,
      height: view.getUint16(28, true) & 0x3fff,
    }
  }

  return null
}

const parseBmpDimensions = (view: DataView): ImageDimensions | null => {
  if (ascii(view, 0, 2) !== "BM" || !hasBytes(view, 18, 8)) return null

  return {
    width: Math.abs(view.getInt32(18, true)),
    height: Math.abs(view.getInt32(22, true)),
  }
}

const readImageDimensions = async (file: File) => {
  const buffer = await file.slice(0, IMAGE_HEADER_BYTES).arrayBuffer()
  const view = new DataView(buffer)

  return (
    parsePngDimensions(view) ??
    parseJpegDimensions(view) ??
    parseGifDimensions(view) ??
    parseWebpDimensions(view) ??
    parseBmpDimensions(view)
  )
}

export const validateImageUpload = async (formData: FormData, field: string) => {
  const value = formData.get(field)
  if (!(value instanceof File) || value.size === 0 || !IMAGE_UPLOAD_MAX_PIXELS) return

  let dimensions: ImageDimensions | null
  try {
    dimensions = await readImageDimensions(value)
  } catch (error) {
    console.debug("Failed to read image dimensions", error)
    throw new Error(t("validation.image_not_readable"))
  }

  if (dimensions && dimensions.width * dimensions.height > IMAGE_UPLOAD_MAX_PIXELS) {
    throw new Error(t("validation.image_too_large"))
  }
}
