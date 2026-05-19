// TODO: Add PDF/SVG only with a non-canvas/vector export path.
export const IMAGE_EXPORT_FORMATS = [
  { mimeType: "image/jpeg", suffix: ".jpg", label: "JPEG" },
  { mimeType: "image/png", suffix: ".png", label: "PNG" },
  { mimeType: "image/webp", suffix: ".webp", label: "WebP" },
] as const

export type ImageExportMimeType = (typeof IMAGE_EXPORT_FORMATS)[number]["mimeType"]

export const isImageExportMimeType = (value: unknown): value is ImageExportMimeType =>
  typeof value === "string" &&
  IMAGE_EXPORT_FORMATS.some((format) => format.mimeType === value)
