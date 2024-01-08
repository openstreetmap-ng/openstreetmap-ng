from annotated_types import Predicate

from src.models.oauth2_code_challenge_method import OAuth2CodeChallengeMethod

CodeChallengeMethodValidator = Predicate(lambda s: s in (e.value for e in OAuth2CodeChallengeMethod))
