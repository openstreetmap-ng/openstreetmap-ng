/**
 * Progressive Image Loading with LQIP (Low Quality Image Placeholder)
 *
 * Handles loading full-resolution images from proxy endpoints while displaying
 * tiny thumbnails. Provides smooth fade-in transition and loading feedback.
 */

interface ProgressiveImageState {
    loading: boolean
    error: boolean
}

const imageStates = new Map<string, ProgressiveImageState>()

/**
 * Initialize progressive image loading for all images in the document.
 * Should be called after diary content is loaded.
 */
export const initializeProgressiveImages = (): void => {
    const containers = document.querySelectorAll<HTMLElement>('.progressive-img')

    for (const container of containers) {
        const proxyId = container.dataset.proxyId
        if (!proxyId) continue

        // Get the thumbnail image (already loaded as base64)
        const thumbnail = container.querySelector<HTMLImageElement>('img.thumbnail')
        if (!thumbnail) continue

        // Don't re-initialize if already processed
        if (imageStates.has(proxyId)) continue

        // Mark as loading
        imageStates.set(proxyId, { loading: true, error: false })

        // Create the full-resolution image element
        const fullImg = document.createElement('img')
        fullImg.className = 'full-img'
        fullImg.loading = 'lazy'
        fullImg.decoding = 'async'

        // Preserve alt text if present
        const altText = thumbnail.alt
        if (altText) {
            fullImg.alt = altText
        }

        // Set the proxy URL for the full image
        fullImg.src = `/api/web/img/proxy/${proxyId}`

        // Add loading class to container for CSS animations
        container.classList.add('loading')

        // Handle successful load
        fullImg.addEventListener('load', () => {
            const state = imageStates.get(proxyId)
            if (state) {
                state.loading = false
            }

            // Add loaded class for fade-in animation
            container.classList.remove('loading')
            container.classList.add('loaded')

            // Replace thumbnail with full image after a brief delay for smooth transition
            setTimeout(() => {
                thumbnail.remove()
                fullImg.classList.add('visible')
            }, 100)
        })

        // Handle load errors
        fullImg.addEventListener('error', () => {
            const state = imageStates.get(proxyId)
            if (state) {
                state.loading = false
                state.error = true
            }

            container.classList.remove('loading')
            container.classList.add('error')

            // Remove thumbnail on error to avoid confusion
            // User will see broken image icon or alt text
            thumbnail.remove()
        })

        // Insert the full image (hidden initially via CSS)
        container.appendChild(fullImg)
    }
}

/**
 * Initialize on diary pages when content is ready.
 * This function is called from main.ts.
 */
export const setupProgressiveImages = (): void => {
    // Initial setup for server-rendered content
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeProgressiveImages)
    } else {
        initializeProgressiveImages()
    }

    // Also watch for dynamically loaded diary comments
    // StandardPagination loads new content, so we need to reinitialize
    const observer = new MutationObserver((mutations) => {
        for (const mutation of mutations) {
            if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                // Check if any added nodes contain progressive images
                for (const node of mutation.addedNodes) {
                    if (node instanceof HTMLElement) {
                        const hasProgressiveImages =
                            node.classList?.contains('progressive-img') ||
                            node.querySelector?.('.progressive-img')

                        if (hasProgressiveImages) {
                            initializeProgressiveImages()
                            break
                        }
                    }
                }
            }
        }
    })

    // Observe the diary content area for changes
    const diaryContent = document.querySelector('.diary-content, .diary-comments')
    if (diaryContent) {
        observer.observe(diaryContent, { childList: true, subtree: true })
    }
}
