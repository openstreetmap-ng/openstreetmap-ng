# <img src="https://files.monicz.dev/osm/openstreetmap-ng.webp" alt="OpenStreetMap-NG logo" height="100px"> OpenStreetMap-NG

![Python version](https://shields.monicz.dev/badge/python-v3.12-blue)
[![Support my work](https://shields.monicz.dev/badge/%E2%99%A5%EF%B8%8F%20Support%20my%20work-purple)](https://monicz.dev/#support-my-work)
[![Liberapay Patrons](https://shields.monicz.dev/liberapay/patrons/Zaczero?logo=liberapay)](https://liberapay.com/Zaczero/)
[![GitHub repo stars](https://shields.monicz.dev/github/stars/Zaczero/openstreetmap-ng?style=social)](https://github.com/Zaczero/openstreetmap-ng)

OpenStreetMap-NG is an unofficial Python fork of [openstreetmap.org](https://openstreetmap.org). It's on a mission to push the boundaries of OpenStreetMap and provide a better experience for all users. It's simply the Next Generation of OpenStreetMap.

🚧 **Active development alert**: Please note that this project is in a very active development. Code is continuously evolving in significant ways. As a result, **I am not currently accepting pull requests and issues**.

## Development Updates 📢

I actively post weekly/bi-weekly updates on the development of OpenStreetMap-NG on my [OpenStreetMap diary](https://www.openstreetmap.org/user/NorthCrab/diary). You can also subscribe to the [RSS feed](https://www.openstreetmap.org/user/NorthCrab/diary/rss) to stay up-to-date.

## The Vision ✨

- **Simple to contribute**: OpenStreetMap-NG requires basic Python knowledge to contribute. There are no complex abstractions or frameworks to learn. We us Nix to significantly simplify the development setup and ensure reproducibility.

- **Super efficient**: OpenStreetMap-NG uses modern programming techniques to provide high performance and low latency. Most of the codebase is compiled to C language with Cython Pure Python Mode.

- **Privacy first**: OpenStreetMap-NG is designed with privacy first approach. We give users the control over their data and privacy. The new builtin proxy for third-party requests protects users identity.

- **Innovation**: OpenStreetMap-NG is a playground for new ideas and features. It's a place where the community can experiment with new features and technologies. We are not afraid of change.

## KISS Principle 🔢

OpenStreetMap-NG follows the KISS principle (Keep It Simple, Stupid). We believe that simplicity is the key to success and that less is more. We avoid complex abstractions and frameworks. We use straightforward and easy to understand Python code.

## Community Driven 🌍

OpenStreetMap-NG is a community-driven project. We welcome contributions from everyone. We believe that the best ideas come from the community!

We are not a part of the OpenStreetMap Foundation.

## Learn More 📚

More details can be found in the project [announcement](https://github.com/Zaczero/openstreetmap-ng/blob/main/ANNOUNCEMENT.md). This information is not strictly up-to-date, but it provides a broader view of the project.

## The Roadmap 🛣️

This is the general roadmap of the OpenStreetMap-NG project. I will update it from time to time to reflect the current state.

- [x] Architecture design
- [x] ~~Migration of the database models (document-db)~~
- [x] Migration of the database models (sql-db)
- [x] Migration of translations
- [x] Migration of various utilities and "lib" folder
- [x] Cache for markdown generated content (faster page loading)
- [x] Migration of OAuth 1.0 & OAuth 2.0
- [x] Authorization
- [ ] Authorization with third-party providers
- [x] Optimistic diff processing
- [x] Migration of API 0.6
- [ ] Migration of redactions
- [x] Migration of rate limiting
- [ ] Migration of changeset history RSS feed
- [x] Improved GPX traces processing
- [40%] Migration of website API
- [x] Migration and refactoring of stylesheets
- [x] Migration and refactoring of scripts
- [40%] Migration of templates
- [ ] 🎉 **FEATURE-PARITY POINT** 🎉
- [x] Development translation overrides
- [ ] Anti-vandalism stage 1
- [x] Redis in-memory caching
- [20%] Pagination and limits
- [ ] Deprecation of OAuth 1.0 warning
- [x] User permalinks
- [x] Proxy for Amazon requests (better privacy)
- [x] Addition of Rapid editor
- [ ] Ability to rotate OAuth keys
- [ ] Scheduled account delete
- [ ] Identification of anonymous note users
- [ ] Anti-vandalism stage 2
- [10%] Design finalization of API 0.7
- [10%] Development of API 0.7
- [ ] 2FA and U2F support
- [ ] Community profiles
- [ ] Functional sitemap.xml
- **And a lot more...** :-)!
