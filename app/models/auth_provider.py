from typing import Literal, get_args

AuthProvider = Literal['google', 'facebook', 'microsoft', 'github', 'wikimedia']
# TODO: openid
# TODO: migration wikimedia, old value: wikipedia

AUTH_PROVIDERS: frozenset[AuthProvider] = frozenset(get_args(AuthProvider))

AuthProviderAction = Literal['login', 'signup', 'settings']
