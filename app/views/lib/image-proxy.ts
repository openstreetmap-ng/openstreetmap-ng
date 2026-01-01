import { decode } from "blurhash"

const imageProxies = document.querySelectorAll("img[data-thumbnail]")
console.debug("ImageProxy: Initializing", imageProxies.length)

if (imageProxies.length) {
    const padding = 48 // Account for padding around the image
    const canvas = document.createElement("canvas")
    const ctx = canvas.getContext("2d")!

    for (const img of imageProxies) {
        const hash = img.dataset.thumbnail!
        const imgWidth = Number.parseInt(img.getAttribute("width")!, 10) - padding
        const imgHeight = Number.parseInt(img.getAttribute("height")!, 10) - padding

        const aspectRatio = imgWidth / imgHeight
        const thumbHeight = 24
        const thumbWidth = Math.round(thumbHeight * aspectRatio)

        // Decode BlurHash to pixel data
        const pixels = decode(hash, thumbWidth, thumbHeight)

        // Resize canvas and render (resizing clears content)
        canvas.width = thumbWidth
        canvas.height = thumbHeight
        const imageData = ctx.createImageData(thumbWidth, thumbHeight)
        imageData.data.set(pixels)
        ctx.putImageData(imageData, 0, 0)

        // Set as background
        img.classList.add("image-proxy-loading")
        img.style.backgroundImage = `url('${canvas.toDataURL()}')`
        img.removeAttribute("data-thumbnail")

        const markLoaded = () => {
            img.classList.remove("image-proxy-loading")
            img.style.backgroundImage = ""

            if (img.naturalWidth !== imgWidth || img.naturalHeight !== imgHeight) {
                img.removeAttribute("width")
                img.removeAttribute("height")
            }
        }

        const markError = () => img.remove()

        if (img.complete) {
            if (img.naturalWidth) markLoaded()
            else markError()
            continue
        }

        img.addEventListener("load", markLoaded, { once: true })
        img.addEventListener("error", markError, { once: true })
    }
}
