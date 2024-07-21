from typing import NamedTuple

from app.config import NAME
from app.models.scope import Scope


class SystemApp(NamedTuple):
    name: str
    client_id: str
    scopes: tuple[Scope, ...]


SYSTEM_APPS = (
    SystemApp(
        name=NAME,
        client_id='SystemApp.web',
        scopes=(Scope.web_user,),
    ),
    SystemApp(
        name='iD',
        client_id='SystemApp.id',
        scopes=(
            Scope.read_prefs,
            Scope.write_prefs,
            Scope.write_api,
            Scope.read_gpx,
            Scope.write_notes,
        ),
    ),
    SystemApp(
        name='Rapid',
        client_id='SystemApp.rapid',
        scopes=(
            Scope.read_prefs,
            Scope.write_prefs,
            Scope.write_api,
            Scope.read_gpx,
            Scope.write_notes,
        ),
    ),
)
