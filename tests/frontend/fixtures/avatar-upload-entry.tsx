import { render } from "preact"
import {
  formDataBytes,
  StandardForm,
} from "../../../app/views/components/standard-form"
const state = window as any
state.rpcCalls = 0
state.readCalls = 0
const originalRead = Blob.prototype.arrayBuffer
Blob.prototype.arrayBuffer = function () {
  state.readCalls++
  return originalRead.call(this)
}
const name = new URLSearchParams(location.search).get("field") ?? "avatar_file"
render(
  <StandardForm
    method={{} as any}
    buildRequest={async ({ formData }) => ({
      file: await formDataBytes(formData, name),
    })}
  >
    <input
      type="file"
      name={name}
      onChange={(event) => event.currentTarget.form!.requestSubmit()}
    />
    <button type="submit">Upload</button>
  </StandardForm>,
  document.getElementById("root")!,
)
