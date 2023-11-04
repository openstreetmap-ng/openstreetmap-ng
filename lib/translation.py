from gettext import GNUTranslations, translation
from typing import Sequence

from cachetools import TTLCache, cached

from config import LOCALE_DOMAIN


@cached(TTLCache(128, ttl=86400))
def get_translation(languages: Sequence[str]) -> GNUTranslations:
    '''
    Get a translation object for the preferred languages.
    '''

    return translation(
        domain=LOCALE_DOMAIN,
        localedir='config/locale',
        languages=languages,
    )
