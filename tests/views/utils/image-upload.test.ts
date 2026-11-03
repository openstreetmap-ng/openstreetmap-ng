import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test"
import { imageUploadBytes } from "../../../app/views/utils/image-upload"

let width = 800,
  height = 600,
  decodeFails = false,
  pending = false,
  revoked: string[] = []
const originalImage = globalThis.Image,
  originalCreateURL = globalThis.URL.createObjectURL,
  originalRevokeURL = globalThis.URL.revokeObjectURL

class BrowserImage extends globalThis.EventTarget {
  naturalWidth = 0
  naturalHeight = 0
  #src = ""
  get src() {
    return this.#src
  }
  set src(value: string) {
    this.#src = value
    if (!value || pending) return
    globalThis.queueMicrotask(() => {
      if (decodeFails) this.dispatchEvent(new globalThis.Event("error"))
      else {
        this.naturalWidth = width
        this.naturalHeight = height
        this.dispatchEvent(new globalThis.Event("load"))
      }
    })
  }
}

beforeEach(() => {
  width = 800
  height = 600
  decodeFails = false
  pending = false
  revoked = []
  globalThis.Image = BrowserImage as unknown as typeof globalThis.Image
  globalThis.URL.createObjectURL = () => "blob:fixture"
  globalThis.URL.revokeObjectURL = (url) => revoked.push(url)
})

afterEach(() => {
  globalThis.Image = originalImage
  globalThis.URL.createObjectURL = originalCreateURL
  globalThis.URL.revokeObjectURL = originalRevokeURL
})

function fixture(size = 3) {
  const controller = new globalThis.AbortController(),
    input = { value: "selected.png" } as HTMLInputElement,
    read = mock(() => Promise.resolve(new Uint8Array([1, 2, 3]).buffer)),
    file = { size, arrayBuffer: read } as unknown as File,
    formData = { get: () => file } as unknown as FormData,
    options = {
      input,
      maxBytes: 100,
      maxPixels: 178_956_970,
      fileError: "localized file error",
      dimensionsError: "localized dimensions error",
      signal: controller.signal,
    }
  return { formData, options, read, input, controller }
}

describe("image upload preflight (explicit browser API fakes)", () => {
  test.each([99, 100, 101])(
    "rejects request-sized file %d before read",
    async (size) => {
      const f = fixture(size)
      await expect(
        imageUploadBytes(f.formData, "avatar_file", f.options),
      ).rejects.toThrow("localized file error")
      expect(f.read).not.toHaveBeenCalled()
      expect(f.input.value).toBe("")
      expect(revoked).toEqual([])
    },
  )

  test("accepts exact serialized request ceiling", async () => {
    const f = fixture(98)
    await imageUploadBytes(f.formData, "avatar_file", f.options)
    expect(f.read).toHaveBeenCalledTimes(1)
  })

  test("accounts for a multibyte protobuf length varint", async () => {
    const f = fixture(128)
    f.options.maxBytes = 130
    await expect(
      imageUploadBytes(f.formData, "avatar_file", f.options),
    ).rejects.toThrow("localized file error")
    expect(f.read).not.toHaveBeenCalled()
  })

  test("preserves normal camera dimensions rather than enforcing output size", async () => {
    const f = fixture()
    width = 6000
    height = 4000
    expect(await imageUploadBytes(f.formData, "avatar_file", f.options)).toEqual(
      new Uint8Array([1, 2, 3]),
    )
    expect(f.read).toHaveBeenCalledTimes(1)
    expect(revoked).toEqual(["blob:fixture"])
  })

  test("accepts the existing hard pixel limit", async () => {
    const f = fixture()
    width = 178_956_970
    height = 1
    await imageUploadBytes(f.formData, "avatar_file", f.options)
    expect(f.read).toHaveBeenCalledTimes(1)
  })

  test("rejects dimensions beyond the hard pixel limit before read", async () => {
    const f = fixture()
    width = 178_956_971
    height = 1
    await expect(
      imageUploadBytes(f.formData, "avatar_file", f.options),
    ).rejects.toThrow("localized dimensions error")
    expect(f.read).not.toHaveBeenCalled()
    expect(f.input.value).toBe("")
    expect(revoked).toEqual(["blob:fixture"])
  })

  test("defers browser-unsupported image formats to Pillow", async () => {
    const f = fixture()
    decodeFails = true
    await imageUploadBytes(f.formData, "avatar_file", f.options)
    expect(f.read).toHaveBeenCalledTimes(1)
    expect(revoked).toEqual(["blob:fixture"])
  })

  test("preserves empty avatar file for preset selection", async () => {
    const f = fixture(0)
    expect(await imageUploadBytes(f.formData, "avatar_file", f.options)).toEqual(
      new Uint8Array(),
    )
    expect(f.read).not.toHaveBeenCalled()
    expect(revoked).toEqual([])
  })

  test("honors a disabled Pillow pixel limit", async () => {
    const f = fixture()
    await imageUploadBytes(f.formData, "avatar_file", { ...f.options, maxPixels: null })
    expect(f.read).toHaveBeenCalledTimes(1)
    expect(revoked).toEqual([])
  })

  test("abort during dimension loading cleans URL and does not read or clear newer input", async () => {
    const f = fixture()
    pending = true
    const result = imageUploadBytes(f.formData, "avatar_file", f.options)
    f.controller.abort()
    await expect(result).rejects.toMatchObject({ name: "AbortError" })
    expect(f.read).not.toHaveBeenCalled()
    expect(f.input.value).toBe("selected.png")
    expect(revoked).toEqual(["blob:fixture"])
  })
})
