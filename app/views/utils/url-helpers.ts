export const isHrefCurrentPage = (
  href: string,
  { includeSubpaths = false }: { includeSubpaths?: boolean } = {},
) => {
  const hrefPathname = new URL(href, window.location.href).pathname
  const locationPathname = window.location.pathname
  return (
    hrefPathname === locationPathname ||
    `${hrefPathname}/` === locationPathname ||
    (includeSubpaths && locationPathname.startsWith(`${hrefPathname}/`))
  )
}

/** Decodes a URL-encoded string, converting both %xx sequences and + characters to their original form */
export const unquotePlus = (str: string) => decodeURIComponent(str.replaceAll("+", " "))
