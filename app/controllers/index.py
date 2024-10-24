from typing import Annotated

from fastapi import APIRouter, Query
from starlette import status
from starlette.responses import FileResponse, RedirectResponse, Response

from app.lib.auth_context import auth_user, web_user
from app.lib.jinja_env import render
from app.lib.local_chapters import LOCAL_CHAPTERS
from app.lib.locale import DEFAULT_LOCALE, is_installed_locale
from app.lib.render_response import render_response
from app.lib.translation import primary_translation_locale, t, translation_context
from app.models.db.user import User
from app.models.types import LocaleCode

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
@router.get('/distance')
async def index():
    return await render_response('index.jinja2')


@router.get('/communities')
async def communities():
    return await render_response('communities.jinja2', {'local_chapters': LOCAL_CHAPTERS})


@router.get('/copyright/{locale:str}')
async def copyright_i18n(locale: LocaleCode):
    if not is_installed_locale(locale):
        return Response(None, status.HTTP_404_NOT_FOUND)
    with translation_context(locale):
        title = t('layouts.copyright')
        copyright_translated_title = t('site.copyright.legal_babble.title_html')
        copyright_content = render('copyright_content.jinja2')
    primary_locale = primary_translation_locale()
    show_notice = locale != primary_locale or primary_locale != DEFAULT_LOCALE
    return await render_response(
        'copyright.jinja2',
        {
            'title': title,
            'copyright_content': copyright_content,
            'copyright_translated_title': copyright_translated_title,
            'show_notice': show_notice,
        },
    )


@router.get('/copyright')
async def copyright_():
    return await copyright_i18n(locale=primary_translation_locale())


@router.get('/about/{locale:str}')
async def about_i18n(locale: LocaleCode):
    if not is_installed_locale(locale):
        return Response(None, status.HTTP_404_NOT_FOUND)
    with translation_context(locale):
        title = t('layouts.about')
        about_content = render('about_content.jinja2')
    return await render_response(
        'about.jinja2',
        {
            'title': title,
            'about_content': about_content,
        },
    )


@router.get('/about')
async def about():
    return await about_i18n(locale=primary_translation_locale())


@router.get('/help')
async def help_():
    return await render_response('help.jinja2')


@router.get('/fixthemap')
async def fixthemap():
    return await render_response('fixthemap.jinja2')


@router.get('/login')
async def login(referer: Annotated[str | None, Query()] = None):
    if auth_user() is not None:
        if not referer or not referer.startswith('/'):
            referer = '/'
        return RedirectResponse(referer, status.HTTP_303_SEE_OTHER)
    return await render_response('user/login.jinja2')


@router.get('/welcome')
async def welcome(_: Annotated[User, web_user()]):
    return await render_response('welcome.jinja2')
