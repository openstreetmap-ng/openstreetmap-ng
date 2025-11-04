import { decode } from "blurhash"

const imageProxies = document.querySelectorAll("img[data-thumbnail]")
console.debug("Initializing", imageProxies.length, "image proxies")

for (const img of imageProxies) {
    const hash = img.dataset.thumbnail
    const width = Number.parseInt(img.getAttribute("width"), 10)
    const height = Number.parseInt(img.getAttribute("height"), 10)

    // Decode BlurHash to pixel data
    const pixels = decode(hash, width, height)

    // Render to canvas
    const canvas = document.createElement("canvas")
    canvas.width = width
    canvas.height = height
    const ctx = canvas.getContext("2d")
    const imageData = ctx.createImageData(width, height)
    imageData.data.set(pixels)
    ctx.putImageData(imageData, 0, 0)

    // Set as background
    img.classList.add("image-proxy-loading")
    img.style.backgroundImage = `url('${canvas.toDataURL()}')`
    img.removeAttribute("data-thumbnail")

    const markLoaded = () => {
        img.classList.remove("image-proxy-loading")
        img.style.backgroundImage = ""

        const specWidth = Number.parseInt(img.getAttribute("width"), 10)
        const specHeight = Number.parseInt(img.getAttribute("height"), 10)
        if (img.naturalWidth !== specWidth || img.naturalHeight !== specHeight) {
            img.removeAttribute("width")
            img.removeAttribute("height")
        }
    }

    const markError = () => img.remove()

    if (img.complete) {
        if (img.naturalWidth) {
            markLoaded()
        } else {
            markError()
        }
    } else {
        img.addEventListener("load", markLoaded, { once: true })
        img.addEventListener("error", markError, { once: true })
    }
}
