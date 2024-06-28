# <img src="https://files.monicz.dev/osm/openstreetmap-ng.webp" alt="OpenStreetMap-NG logo" align="left" height="96px"> OpenStreetMap-NG

![Python version](https://shields.monicz.dev/badge/python-v3.12-blue)
[![Discord Developers Chat](https://shields.monicz.dev/discord/1246123404613128203?logo=discord&logoColor=FFF&label=Developers&color=5865F2&cacheSeconds=600)](https://discord.gg/GM89hdjSCB)
[![Liberapay Patrons](https://shields.monicz.dev/liberapay/patrons/Zaczero?logo=liberapay&label=Patrons)](https://liberapay.com/Zaczero/)
[![GitHub repo stars](https://shields.monicz.dev/github/stars/Zaczero/openstreetmap-ng?style=social)](https://github.com/Zaczero/openstreetmap-ng)

OpenStreetMap-NG is an unofficial Python fork of [openstreetmap.org](https://openstreetmap.org). It's on a mission to push the boundaries of OpenStreetMap and provide a better experience for all users. It's simply the Next Generation of OpenStreetMap.

## 📢 Development Updates

I actively post weekly/bi-weekly updates on the development of OpenStreetMap-NG on my [OpenStreetMap diary](https://www.openstreetmap.org/user/NorthCrab/diary). You can also subscribe to the [RSS feed](https://www.openstreetmap.org/user/NorthCrab/diary/rss) to stay up-to-date.

## 👷 Contributing

To get started contributing, see the [Contributing Guide](https://github.com/Zaczero/openstreetmap-ng/wiki/Contributing:-Getting-Started) on the GitHub wiki. This wiki is the primary source of information for contributors. We support Linux, macOS, and Windows (WSL2) operating systems.

You can also join our [Discord server](https://discord.gg/GM89hdjSCB) to receive personalized support and discuss development topics. This is our primary internal communication channel. It's free to join and we're always happy to help you get started!

## ✨ The Vision

- **Simple to contribute**: OpenStreetMap-NG requires just basic Python knowledge to contribute. There are no complex abstractions or frameworks to learn. We use Nix to provide stress-free and streamlined developer experience on all platforms.

- **Super efficient**: OpenStreetMap-NG uses modern programming techniques to provide high performance and low latency. Most of the codebase is compiled to C language with Cython's [Pure Python Mode](https://cython.readthedocs.io/en/latest/src/tutorial/pure.html).

- **Privacy first**: OpenStreetMap-NG is designed with privacy first approach. We give users the control over their data and privacy. The new builtin proxy for third-party requests additionally protects users identity.

- **Innovation**: OpenStreetMap-NG is a playground for new ideas and features. It's a place where the community can experiment with new features and technologies. We are not afraid of change!

## 🔢 KISS Principle

OpenStreetMap-NG follows the KISS principle (Keep It Simple, Stupid). We believe that simplicity is the key to success and that less is more. We avoid complex abstractions and frameworks. We use straightforward and easy to understand Python code.

## 🌍 Community Driven

OpenStreetMap-NG is an open community-driven project. The best ideas come from people just like you! We believe the community is the heart of OpenStreetMap and that everyone should have an equal say.

This project is currently funded through community donations. We are not sponsored nor endorsed by the OpenStreetMap Foundation. We are ordinary mappers who want to make a difference.

## 📚 Learn More

More feature details can be found in the project [announcement](https://github.com/Zaczero/openstreetmap-ng/blob/main/ANNOUNCEMENT.md). This information is not strictly up-to-date, but it provides a broader view of the project. More recent updates can be found on my [OpenStreetMap diary](https://www.openstreetmap.org/user/NorthCrab/diary) but they are lesser in quantity.

## 🛣️ The Roadmap

The general roadmap of the project. You can use it to track the big picture progress. I update it from time to time as the development progresses. Not all features and improvements are listed here.

- ✅ Architecture design
- ✅ Migration of the database models
- ✅ Migration of translations
- ✅ Migration of various utilities and "lib" folder
- ✅ Cache for markdown generated content (faster page loading)
- ✅ Migration of OAuth 1.0 & OAuth 2.0
- ✅ Authorization
- ⬛ Authorization with third-party providers
- ✅ Optimistic diff processing
- ✅ Migration of API 0.6
- ⬛ Migration of redactions
- ✅ Migration of rate limiting
- ⬛ Migration of changeset history RSS feed
- ✅ Improved GPX traces processing
- [70%] Migration of website API
- ✅ Migration and refactoring of stylesheets
- ✅ Migration and refactoring of scripts
- [70%] Migration of templates
- ⬛ 🎉 **FEATURE-PARITY POINT** 🎉
- ✅ Development translation overrides
- [20%] Anti-vandalism stage 1
- ✅ Redis in-memory caching
- [40%] Pagination and limits
- ⬛ Deprecation of OAuth 1.0 warning
- ✅ User permalinks
- ✅ Proxy for Amazon requests (better privacy)
- ✅ Addition of Rapid editor
- ⬛ Ability to rotate OAuth keys
- ⬛ Scheduled account delete
- ⬛ Identification of anonymous note users
- ⬛ Anti-vandalism stage 2
- [30%] Design finalization of API 0.7
- [10%] Development of API 0.7
- [10%] 2FA and U2F support
- ⬛ Community profiles
- ⬛ Functional sitemap.xml
- **And a lot more...** :-)!

---

<p align="center">
<i>OpenStreetMap-NG</i><br>
<i>Made with love and care.</i><br>
— 🫂 —
</p>
