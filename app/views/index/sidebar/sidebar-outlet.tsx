import { LayersSidebar } from "@index/sidebar/layers"
import { LegendSidebar } from "@index/sidebar/legend"
import { ShareSidebar } from "@index/sidebar/share"
import { rightSidebar } from "@lib/map/main-map"

export const RightSidebarOutlet = () => {
  const activeKind = rightSidebar.value
  if (!activeKind) return null

  const close = () => (rightSidebar.value = null)

  return (
    <div class="sidebar">
      <div class={`map-sidebar ${activeKind}`}>
        {activeKind === "layers" ? (
          <LayersSidebar close={close} />
        ) : activeKind === "legend" ? (
          <LegendSidebar close={close} />
        ) : (
          <ShareSidebar close={close} />
        )}
      </div>
    </div>
  )
}
