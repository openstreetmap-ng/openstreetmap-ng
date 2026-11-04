# Software directory artwork and editorial sources

`organicmaps.svg` and `maptiler.svg` are unmodified icons from Simple Icons
16.12.0 (`https://github.com/simple-icons/simple-icons`, CC0-1.0). Brand names
and trademarks remain their owners' property. They identify the applications;
their inclusion does not imply endorsement. Other cards reuse the existing
local iD, JOSM and Overpass artwork in `../brand/`.

The initial catalog in `app/lib/software.py` was reviewed on 2026-10-28:

- iD: https://github.com/openstreetmap/iD (ISC)
- JOSM: https://josm.openstreetmap.de/ (GPL; desktop downloads linked there)
- Overpass turbo: https://github.com/tyrasd/overpass-turbo (MIT)
- Organic Maps: https://organicmaps.app/ (Apache-2.0; stable Android/iOS,
  with Linux desktop beta deliberately excluded from stable platform filters)
- MapTiler Engine: https://www.maptiler.com/engine/ (supports OSM input),
  https://docs.maptiler.com/engine/installation/ (platform requirements),
  https://www.maptiler.com/terms/engine/ (proprietary, plan-specific terms).
  This is the Engine product, not MapTiler's open-source SDKs. Current macOS
  requirements are disclosed in the description.

`maintained` means the project is currently supported/developed; it is not a
support guarantee. `unmaintained` is available for future editorial updates;
the initial catalog contains no discontinued projects. Recheck the sources
when updating descriptions, platforms, licenses or status. Add local artwork
and translations alongside each new entry. The page makes no remote requests
to load its catalog or images and its GET filters work without JavaScript.
