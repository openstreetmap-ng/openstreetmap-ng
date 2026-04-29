import type { StandardPaginationStateValid } from "@lib/proto/shared_pb"

export const copyArrayToClipboard = async (items: readonly string[]) => {
  try {
    await navigator.clipboard.writeText(`[${items.join(",")}]`)
  } catch (error) {
    alert(error.message)
  }
}

export const exportJsonFile = (fileName: string, value: unknown) => {
  const blob = new Blob([JSON.stringify(value)], { type: "application/json" })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = fileName
  document.body.append(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

export const totalItemsFromPaginationState = (state: StandardPaginationStateValid) => {
  const { totalExtent } = state
  switch (totalExtent.case) {
    case "knownTotal":
      return totalExtent.value.numItems.toString()
    case "maxDiscoveredPage":
      return `${Math.max(1, (totalExtent.value - 1) * state.pageSize)}+`
    default:
      throw new Error("Missing pagination total extent")
  }
}

export const FilterActions = ({
  totalItems,
  totalLabel,
  onCopyPage,
  onExportAll,
  onClear,
}: {
  totalItems: string | null
  totalLabel: string
  onCopyPage: () => void | Promise<void>
  onExportAll: () => void | Promise<void>
  onClear: () => void
}) => (
  <div class="d-flex justify-content-between align-items-center">
    <div
      class="btn-group"
      role="group"
    >
      <button
        type="button"
        class="btn btn-sm btn-outline-secondary"
        onClick={onCopyPage}
      >
        <i class="bi bi-clipboard" /> Copy page
      </button>
      <button
        type="button"
        class="btn btn-sm btn-outline-secondary"
        onClick={onExportAll}
      >
        <i class="bi bi-download" /> Export all
      </button>
    </div>

    <div>
      <span class="text-muted me-2">
        {totalItems ?? "…"} {totalLabel}
      </span>
      <div
        class="btn-group"
        role="group"
      >
        <button
          type="submit"
          class="btn btn-outline-primary"
        >
          <i class="bi bi-funnel" /> Apply
        </button>
        <button
          type="button"
          class="btn btn-outline-secondary"
          onClick={onClear}
        >
          <i class="bi bi-arrow-counterclockwise" /> Clear
        </button>
      </div>
    </div>
  </div>
)
