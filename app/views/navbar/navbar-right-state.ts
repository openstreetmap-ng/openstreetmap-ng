import { signal } from "@preact/signals"
import { config } from "@utils/config"

export const messagesCountUnread = signal(config.userConfig?.messagesCountUnread ?? 0)
