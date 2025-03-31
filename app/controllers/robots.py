from fastapi import APIRouter, Response

from app.config import ENV

router = APIRouter()


_RESPONSE = Response(
    (
        """
User-agent: *
Disallow: /api
Disallow: /changeset
Disallow: */diary/comments
Disallow: /edit
Disallow: /export/embed.html
Disallow: */history
Disallow: /note
Allow: /note/new
Disallow: */notes
Disallow: /redactions
Disallow: /search
Disallow: /trace
Disallow: */traces
Disallow: /user_blocks
"""
        if ENV == 'prod'
        else """
User-agent: *
Disallow: /
"""
    ).lstrip(),
    media_type='text/plain',
)


@router.get('/robots.txt')
async def robots():
    return _RESPONSE
