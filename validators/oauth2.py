from annotated_types import Predicate

from models.oauth2_code_challenge_method import OAuth2CodeChallengeMethod

CodeChallengeMethodValidator = Predicate(lambda s: s in map(lambda e: e.value, OAuth2CodeChallengeMethod))
