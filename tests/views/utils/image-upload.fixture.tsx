import { StandardForm } from "@components/standard-form"
import { imageFormDataBytes } from "@utils/image-upload"
import { init } from "i18next"
import { render } from "preact"
import { useRef } from "preact/hooks"

await init({
  lng: "en",
  resources: {
    en: {
      translation: {
        validation: {
          image_file_too_big: "Image file is too large. Please choose a smaller image.",
        },
        javascripts: { close: "Close" },
      },
    },
  },
})

Object.assign(window, { uploads: 0, bytesRead: 0, uploadSize: 0, failUpload: false })
const read = File.prototype.arrayBuffer
File.prototype.arrayBuffer = function () {
  ;(window as any).bytesRead++
  return read.call(this)
}

const Upload = () => {
  const input = useRef<HTMLInputElement>(null)
  return (
    <StandardForm
      method={{} as any}
      buildRequest={async ({ formData }) => ({
        image: await imageFormDataBytes(formData, "image", input.current!),
      })}
      onError={() => {
        input.current!.value = ""
      }}
    >
      <input
        id="image"
        ref={input}
        class="visually-hidden"
        type="file"
        name="image"
        accept="image/*"
        onChange={(event) => event.currentTarget.form!.requestSubmit()}
      />
      <button
        type="button"
        onClick={() => input.current!.click()}
      >
        Upload image
      </button>
    </StandardForm>
  )
}
render(<Upload />, document.querySelector("main")!)
