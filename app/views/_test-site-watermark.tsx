import { ENV } from "@lib/config"
import { render } from "preact"

if (ENV === "test") {
  const root = document.createElement("div")
  document.body.append(root)
  render(
    <div class="test-site-watermark">
      <p>TEST SITE</p>
      <p>Not an official product</p>
    </div>,
    root,
  )
}
