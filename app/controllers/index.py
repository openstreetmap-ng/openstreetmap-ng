from typing import Annotated

from fastapi import APIRouter
from starlette import status
from starlette.responses import FileResponse, RedirectResponse, Response

from app.config import DEFAULT_LANGUAGE
from app.lib.auth_context import auth_user, web_user
from app.lib.local_chapters import LOCAL_CHAPTERS
from app.lib.locale import is_valid_locale
from app.lib.render_response import render_response
from app.lib.translation import primary_translation_language, t, translation_context
from app.models.db.user import User

router = APIRouter()


@router.get('/robots.txt')
async def robots():
    return FileResponse('app/static/robots.txt', media_type='text/plain')


@router.get('/')
@router.get('/export')
@router.get('/directions')
@router.get('/search')
@router.get('/query')
@router.get('/history')
@router.get('/history/nearby')
@router.get('/history/friends')
@router.get('/user/{_:str}/history')
@router.get('/note/new')
@router.get('/note/{_:int}')
@router.get('/changeset/{_:int}')
@router.get('/node/{_:int}')
@router.get('/node/{_:int}/history')
@router.get('/node/{_:int}/history/{__:int}')
@router.get('/way/{_:int}')
@router.get('/way/{_:int}/history')
@router.get('/way/{_:int}/history/{__:int}')
@router.get('/relation/{_:int}')
@router.get('/relation/{_:int}/history')
@router.get('/relation/{_:int}/history/{__:int}')
async def index():
    return render_response('index.jinja2')


@router.get('/communities')
async def communities():
    return render_response('communities.jinja2', {'local_chapters': LOCAL_CHAPTERS})


@router.get('/copyright/{locale:str}')
async def copyright_i18n(locale: str):
    if not is_valid_locale(locale):
        return Response(None, status.HTTP_404_NOT_FOUND)
    with translation_context(primary_translation_language()):
        copyright_notice_title = t('site.copyright.foreign.title')
        original_copyright_link_text = t('site.copyright.foreign.english_link')
        original_copyright_link = f'<a href="/copyright/en">{original_copyright_link_text}</a>'
        copyright_notice_html = t('site.copyright.foreign.html', english_original_link=original_copyright_link)
    with translation_context(locale):
        return render_response(
            'copyright.jinja2',
            dict(
                should_show_notice=locale != primary_translation_language()
                or primary_translation_language() != DEFAULT_LANGUAGE,
                copyright_notice_title=copyright_notice_title,
                copyright_notice_html=copyright_notice_html,
            ),
        )


@router.get('/copyright')
async def copyright_():
    return await copyright_i18n(locale=primary_translation_language())


@router.get('/help')
async def help_():
    return render_response('help.jinja2')


@router.get('/about/{locale:str}')
async def about_i18n(locale: str):
    if not is_valid_locale(locale):
        return Response(None, status.HTTP_404_NOT_FOUND)
    with translation_context(locale):
        return render_response('about.jinja2')


@router.get('/about')
async def about():
    return await about_i18n(locale=primary_translation_language())


@router.get('/fixthemap')
async def fixthemap():
    return render_response('fixthemap.jinja2')


@router.get('/login')
async def login():
    if auth_user() is not None:
        return RedirectResponse('/', status.HTTP_303_SEE_OTHER)
    return render_response('user/login.jinja2')


@router.get('/signup')
async def signup():
    if auth_user() is not None:
        return RedirectResponse('/', status.HTTP_303_SEE_OTHER)
    return render_response('user/signup.jinja2')


@router.get('/welcome')
async def welcome(_: Annotated[User, web_user()]):
    return render_response('welcome.jinja2')


@router.get('/settings')
async def settings(_: Annotated[User, web_user()]):
    return render_response('user/settings/index.jinja2')
