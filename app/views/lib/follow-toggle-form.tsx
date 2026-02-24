import { Service } from "@lib/proto/follow_pb"
import { StandardForm } from "@lib/standard-form"
import type { Signal } from "@preact/signals"
import type { ComponentChildren } from "preact"

export const FollowToggleForm = ({
  targetUserId,
  isFollowing,
  class: className = "",
  children,
}: {
  targetUserId: bigint
  isFollowing: Signal<boolean>
  class?: string
  children: (ctx: Readonly<{ isFollowing: boolean }>) => ComponentChildren
}) => (
  <StandardForm
    method={Service.method.update}
    buildRequest={() => ({
      targetUserId,
      isFollowing: !isFollowing.value,
    })}
    onSuccess={(_, ctx) => (isFollowing.value = ctx.request.isFollowing)}
  >
    <button
      type="submit"
      class={className}
    >
      {children({ isFollowing: isFollowing.value })}
    </button>
  </StandardForm>
)
