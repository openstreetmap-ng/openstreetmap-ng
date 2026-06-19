// Canvas-backed map export only supports raster image formats.
// TODO(#36): add PDF/SVG after they have dedicated non-canvas exporters.
export const SHARE_IMAGE_FORMATS = [
  { mimeType: "image/jpeg", suffix: ".jpg", label: "JPEG" },
  { mimeType: "image/png", suffix: ".png", label: "PNG" },
  { mimeType: "image/webp", suffix: ".webp", label: "WebP" },
] as const

export const DEFAULT_SHARE_IMAGE_MIME_TYPE = SHARE_IMAGE_FORMATS[0].mimeType

export const getShareImageFormat = (mimeType: string) =>
  SHARE_IMAGE_FORMATS.find((format) => format.mimeType === mimeType) ??
  SHARE_IMAGE_FORMATS[0]

export const isShareImageMimeType = (mimeType: string) =>
  SHARE_IMAGE_FORMATS.some((format) => format.mimeType === mimeType)
