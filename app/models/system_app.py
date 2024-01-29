from collections.abc import Sequence
from enum import StrEnum
from typing import Self

from models.scope import Scope


class SystemApp(StrEnum):
    id = 'id'
    rapid = 'rapid'

    # TODO: put it in a better place?
    @classmethod
    def scopes(cls, app: Self) -> Sequence[Scope]:
        """
        Get the oauth scopes for the given app.

        >>> SystemApp.scopes(SystemApp.id)
        [Scope.read_prefs, Scope.write_prefs, Scope.write_api, Scope.read_gpx, Scope.write_notes]
        """

        if app == cls.id:  # noqa: SIM114
            return (
                Scope.read_prefs,
                Scope.write_prefs,
                Scope.write_api,
                Scope.read_gpx,
                Scope.write_notes,
            )
        elif app == cls.rapid:
            return (
                Scope.read_prefs,
                Scope.write_prefs,
                Scope.write_api,
                Scope.read_gpx,
                Scope.write_notes,
            )
        else:
            raise NotImplementedError(f'Unsupported system app {app!r}')
