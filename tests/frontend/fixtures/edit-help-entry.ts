import {
  configureRouter,
  defineRoute,
  routerCtx,
} from "../../../app/views/index/router"
import "../../../app/views/navbar/navbar-left"
configureRouter([
  defineRoute({ id: "test", path: ["/", "/history", "/edit"], Component: () => null }),
])
Object.assign(window, {
  navigate: (url: string) => {
    const anchor = document.createElement("a")
    anchor.href = url
    document.body.append(anchor)
    anchor.click()
    anchor.remove()
  },
  routerCtx,
})
