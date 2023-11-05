# <img src="https://files.monicz.dev/osm/openstreetmap-ng.webp" alt="OpenStreetMap-NG logo" height="100px"> OpenStreetMap-NG

Welcome to the next generation of OpenStreetMap, an improved website and API developed in Python!

🚧 **Active development alert**: Please note that this project is in a very active development. Code is continuously evolving, and significant changes are happening daily. As a result, **I am not currently accepting pull requests**.

This is one of my most significant undertakings to date, and I have put all my heart and soul into it. My goal is not just to benefit myself but to create something incredible for our entire community. It's time to give OpenStreetMap the love and attention it truly deserves. This document is here to guide you through the exciting new features—there's quite a lot!

📢 **One final announcement**. I am now a full-time FOSS (Free and Open Source Software) developer. This is a dream I've had for a long time, and it's time to make it into reality. After you've finished reading, I kindly ask you to consider supporting me with a small monthly contribution. Your support will enable me to continue my work on OpenStreetMap, making it even better. **This project is my testimony.**

Support with [Liberapay](https://liberapay.com/Zaczero), [GitHub](https://github.com/sponsors/Zaczero) or [Patreon](https://patreon.com/Zaczero).

🎥 **Tired of reading? Listen instead!** For those who prefer to listen instead of reading, a detailed video announcement about the project is available. You can watch the 1-hour long talk [here](https://peertube.monicz.dev/w/mYar3DqYk4wMCDjVdAbtNH).

❗ **Disclaimer**: Please note that this project is not affiliated with the OpenStreetMap Foundation. It's the result of my voluntary work and personal choices.

## Principles

Let's begin by establishing the core principles that lead the changes introduced in this release:

1. **Community-driven** - The primary goal is to ensure that the project is accessible to a broad audience. We must make it easy for individuals to contribute, even if they don't possess extensive expertise.

2. **Developers-focused** - One must value the time of developers and aim to provide a stable and predictable API interface. The goal is to simplify the process of integration into existing client solutions, making it seamless and convenient.

3. **Privacy-minded** - The software must respect the privacy and freedom of its users. The users control the program; the program does not control the users.

## The New Architecture

The OpenStreetMap project has undergone a significant architecture overhaul to make it more accessible for community contributions. Previously, the Ruby-based setup presented various obstacles for new contributors:

- Required understanding of multiple languages (Ruby, SQL and C++).
- Involved convoluted and poorly-documented code.
- Forced duplication of effort—API 0.6 code had to be written twice, once in Ruby and another time in C++.

### Programming Languages: Before and After

| Old Stack                                                                                                         | New Stack                                                                                                    |
| ----------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/ruby/ruby-original.svg" height="16"> Ruby            | <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/python/python-original.svg" height="16"> Python |
| <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/cplusplus/cplusplus-original.svg" height="16"> C++   |                                                                                                              |
| <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/postgresql/postgresql-original.svg" height="16"> SQL |                                                                                                              |

**Notice**: I am considering a switch to PostgreSQL having received the community feedback, I will post more updates soon!

### Database: MongoDB

OpenStreetMap-NG leverages MongoDB as its NoSQL database engine. Compared to the old SQL-based approach, MongoDB offers:

- **Simple syntax**: It feels like working with a JSON file, making it easier to understand.
- **Operational flexibility**: Supports all key operations and allows efficient spatial data filtering.
- **Clean and readable code**: The database structure is intuitive, making the codebase more maintainable.

This architecture transformation not only simplifies the code but also makes it easier for more people to contribute, thereby ensuring that OpenStreetMap remains an open community-driven project.

### What Does It Mean? (less-technical)

The new architecture brings a lot of advantages that make it easier for more people to get involved in the OpenStreetMap project. Here's what this all means in simpler terms:

- **Easier to Understand**: OpenStreetMap-NG switches from Ruby/C++ to Python, which is known for its simplicity. Many people find Python easier to learn and work with, making the project more accessible for newcomers.

- **Less Complexity**: Previously, if you wanted to contribute, you had to understand and write code in multiple languages—Ruby and C++. Now, you only need to focus on Python, significantly simplifying the learning curve.

- **New Opportunities for Rapid Innovation**: The shift to Python opens up a wide array of new opportunities for quick and effective solutions. Python's extensive libraries and frameworks make it easier to introduce new features and capabilities into the project at a much faster pace.

- **Simpler and More Flexible Database**: OpenStreetMap-NG transitions from a traditional SQL database to MongoDB. For those contributing to the project, MongoDB is simpler to understand and work with. The models also are designed to be easily extended or modified, adapting more readily to the project's changing needs.

- **Extensible and Flexible**: The new system is designed from the ground up to be easily extensible. As technology evolves or new features are needed, it will be much simpler to integrate those updates.

- **Community-Friendly**: With the lowered barrier to entry and simplified process, more people can contribute to OpenStreetMap. This ensures that it remains an open, community-driven platform.

## Backwards Compatibility and Stability

Understanding the importance of both backwards compatibility and stability, I'm pleased to announce that OpenStreetMap-NG **is backwards compatible** with the previous Ruby version. Here's how I am ensuring a seamless and smooth transition:

- **Test Migration**: All software tests from the Ruby version are being actively ported to the NG release.
- **Additional Tests**: Beyond that, I am introducing new tests to cover even more quirky scenarios.
- **Unchanged Behavior**: Even the weirdest behaviors will remain consistent, ensuring maximum compatibility.

The test migration will be considered complete only after achieving feature-parity with the Ruby version, making sure nothing is left behind. So, rest assured—stability is a #1 priority and not something you'll need to worry about as we move forward.

## New API 0.7

Let's address the elephant in the room. The existing API 0.6 has proven to be challenging to work with, both for API developers and client developers. It feels like every endpoint follows different rules, has its own set of error messages, and behaves inconsistently - making it a headache for everyone involved. It's evident that it was not initially designed with security and safety in mind. At this stage, it makes more sense to start fresh rather than trying to fix the complexities of API 0.6.

The primary goal of API 0.7 is to provide a robust, secure, and predictable interface for interacting with the database. It doesn't alter the fundamental concepts of OSM; instead, it refines them. The good news is that API versions 0.6 and 0.7 are compatible with each other. For example, an object created using API 0.6 can be retrieved using API 0.7. The new API is not only simpler to understand, implement, and use but also more efficient!

While I'm still evaluating the final design of API 0.7, here are some of the proposed changes:

### JSON-First

One of the notable improvements in API 0.7 is the project's focus on simplicity and efficiency. JSON is now the default language for data retrieval and uploads (including map diffs). It's a widely recognized format that ensures ease of use. For those who prefer other formats like XML or RSS, you can still obtain data in your preferred format by adding a simple query parameter, such as `&format=xml`.

### Simpler Diffs

API 0.7 simplifies the process of making changes to elements. It abandons the need for explicit "create" and "delete" actions. All element diffs are now treated as modifications. To create an element, simply set its version to 1. To delete an element, set its visibility to false. This streamlines the osmChange format and reduces the number of API endpoints, making development more straightforward.

### Sane Rules

To ensure better consistency, changesets using the new interface must include two mandatory tags: <kbd>created_by</kbd> and <kbd>comment</kbd>. Once added, these tags cannot be removed in subsequent changeset updates, but you can modify them as needed. Additionally, the new API disallows empty relations and empty or single-node ways when visibility is true. Lastly, empty-key or empty-value tags are forbidden and will also result in an error.

### Simpler Changeset Workflow

A new endpoint has been added that consolidates the functionalities of changeset/create, changeset/#id/upload, and changeset/#id/close into a single streamlined workflow. This ensures that a changeset is created only if the diff upload is successful, reducing the number of API calls from three to one. This improvement benefits many low-complexity applications and popular editors like iD and Rapid. Of course, the standard workflow is still available for applications that require it, such as JOSM and StreetComplete.

### Query at Any Point in Time

With the new API interface, you can now query the map state at any given point in time. This addition opens up exciting possibilities for data visualization and allows you to lock queries to specific moments, enabling the retrieval of multiple sets of information without concerns about inconsistencies.

### Database Cursors

In the future, when a single element has thousands of versions, the API needs an efficient way to query this information. Enter database cursors. Now, each query returns only a limited number of entries (e.g., the first 100 versions) and an additional cursor field. You can pass the cursor value to subsequent requests to continue processing the remaining elements. This feature relies on the new query-at-any-point-in-time functionality to ensure consistent results over extended periods. The cursor has been implemented to remain highly efficient, even when handling elements with millions of versions.

#### Example

1. `/map&bbox=1,2,3,4`: `[1-100 elements, cursor: "aaaaaa"]`
2. `/map&bbox=1,2,3,4&cursor=aaaaaa`: `[101-200 elements, cursor: "bbbbbb"]`
3. `/map&bbox=1,2,3,4&cursor=bbbbbb`: `[201-300 elements, cursor: "cccccc"]`
4. and so on...

### Simple Overpass-like Filtering

_(This feature is still under consideration, I need to ensure disk space for index storage will not be an issue here.)_

API 0.7 in OpenStreetMap-NG introduces efficient, [overpass-like](https://wiki.openstreetmap.org/wiki/Overpass_API/Overpass_QL) filtering options for downloading specific map information. This is ideal for users who need to narrow down their API queries without resorting to complex configurations. However, for those requiring more intricate filtering, using Overpass or other specialized tools is advised.

#### Example Filters

- `&filter=node[emergency=defibrillator]` \
  Node defibrillators

- `&filter=nwr[building][addr:city];node[natural!=tree]` \
  Buildings with a city address + nodes that aren't trees

- `&filter=rel[boundary](123456,789012)` \
  Relation boundaries with IDs 123456 and 789012

#### Limitations

There are some limitations to this simple filtering. For example, regex is not supported, and queries are strongly limited in size. The filtering system is primarily meant for prototyping or low-complexity applications, such as map editors looking to edit just a specific kind of data.

### Query by Simple Polygons

While standard bounding boxes are supported in the API 0.7, you can also perform queries using arbitrary simple polygons (initially with 3 or 4 vertices). This feature is primarily intended for mobile applications like StreetComplete, which provide map rotation functionality that more often than not, doesn't produce simple W,S,E,N bounding boxes. However, other applications may also find this feature useful. It's worth noting that this feature is not computationally expensive for the server.

### New Ease-of-Life Endpoints

The new API comes with numerous ease-of-life endpoints designed to make your experience smoother and more enjoyable. These endpoints are based on my past year of intense OSM programming experience. For example, one of the new endpoints allows you to efficiently check whether a list of element versions you provide are still the latest ones. Another endpoint lets you download element information before and after a given changeset, essentially providing a proper changeset diff.

### Standardized Errors

API 0.7 introduces a clear and standardized set of errors and behaviors. Whether you're operating on map data, user notes, GPX traces, or any other aspect, you can expect consistent behavior. For instance, when a requested object is not found, you can rely on a standardized error response. While this improvement might not be the most eye-catching, it will significantly enhance the usability of the API.

## Anti-Vandalism

One of the key features of this project is the commitment to preventing map vandalism. The approach is divided into several stages to ensure effective organization and prioritization of short-term wins when they matter most.

<img src="https://files.monicz.dev/osm/anti-vandalism-hardening.webp?cachebuster" alt="Anti-Vandalism Procedure Visualized" width="70%">

### Stage 1, Ready on Release

- **Invisible Proof-of-Work Captcha**: An invisible proof-of-work captcha has been added to the user registration process. This privacy-friendly captcha doesn't collect any user information. It functions by issuing and verifying a mathematical computation task that complicates the writing of scripts and bots.

- **Blocking Disposable Email Services**: To enhance security, the project disallows the use of some disposable email services.

### Stage 2, Shortly After

- **Adaptive Rate Limit**: To prevent abuse, an adaptive rate limit for map changes is implemented. New users are initially limited to a reasonable number of changes in short periods, with the limit increasing as users gain mapping experience. If the limit is exceeded, an automatic account block is activated, and the moderation team is alerted to manually verify the account's activity.

- **Direct Integration with osm-revert**: The project integrates the [osm-revert](https://github.com/Zaczero/osm-revert) tool directly into the API, making it exclusively available to the moderation team. This integration significantly reduces mass-revert times, cutting them from hours to just minutes. Most of the delays previously faced, such as synchronization issues, rate limits, and conflicts with other mappers, are resolved by connecting osm-revert directly to the database.

### Stage 3, Next-Year Plans

- **Pro-Active Vandalism Migitation**: The adaptive rate limit gets replaced with a smarter metric that takes into account factors like timing, the nature and quality of changes, and more. This new metric powers an AI model trained to proactively detect vandalism, using historical OpenStreetMap data and past moderation actions for training. The model self-updates daily to stay current with the latest map events. A new dashboard allows the moderation team to oversee the AI's decisions and adjust settings in real-time, enhancing overall map integrity.

I am confident in my ability to deliver on this project, especially given my past experience in creating AI-powered tools for OpenStreetMap. This experience includes developing [osm-yolo-crossings](https://github.com/Zaczero/osm-yolo-crossings) for automatic visual detection and import of zebra crossings, and [osm-budynki-orto-import](https://github.com/Zaczero/osm-budynki-orto-import) for automated validation and import of buildings in Poland. My expertise also extends to various AI applications beyond the scope of OpenStreetMap.

## Optimistic Diff Processing

Introducing one of the most significant new features: the optimistic diff processing algorithm. This algorithm brings a substantial boost to map update throughput, enabling parallel processing while maintaining consistency. In the original system, only one map diff could be processed at a time, causing a significant bottleneck, especially when dealing with sizable changesets of 10,000 elements. With the optimistic diff processing algorithm, this limitation is a thing of the past.

### How Does It Work?

Let's take a simplified look at how the original and new diff processing methods compare. The key goal here is to minimize the total time spent inside a database lock, resulting in higher throughput and a more responsive database.

**Legend**: \
⚡ or no icon is fast, 🐢 is moderate, 🐌 is slow \
🔒 indicates points in the process where the database is locked

#### Original Method

1. Lock database
2. 🔒 🐌 Lookup database and perform precondition checks
3. 🔒 🐢 Create database objects
4. 🔒 Assign sequential IDs
5. 🔒 Insert new data into the database
6. Free the database lock

#### Optimistic Method

1. 🐌 Lookup database and perform precondition checks
2. 🐢 Create database objects
3. Lock database
4. 🔒 ⚡ Quickly look up the database and check if the diff state remains unchanged \
   4.1. If any of the state elments have changed, free the lock and retry the entire operation from step 1. This is why it's called "optimistic" – it assumes that two map diffs operate on disjoint sets of elements (disjoint regions of the map), which is true most of the time.
5. 🔒 Assign sequential IDs
6. 🔒 Insert new data into the database
7. Free the database lock

In the optimistic method, the most resource-intensive operations, such as database lookups, precondition checks, and database object serialization, are performed without acquiring the lock. This algorithm aligns perfectly with the OpenStreetMap operation model, resulting in significant performance improvements.

## Rapid Editor

[<img src="https://files.monicz.dev/osm/rapid.webp" alt="Rapid Editor logo" height="80">](https://rapideditor.org/)

Rapid Editor is now available as an optionally configurable default OSM editor, and it can also be accessed from the Edit dropdown menu. This editor has been known in the community for some time, and it's time for it to receive some deserved recognition.

Users looking to switch the default editor, are presented with a friendly selection screen, comparing various options with short descriptions.

## Scheduled Account Delete

To enhance security and prevent accidental account deletions, a scheduled account delete feature has been added. Instead of deleting the user account immediately, a delay of 1 week is induced, during which users have the ability to cancel the account deletion. An email notification is also sent to the user, providing details of the deletion procedure.

## Better Privacy

I never like when some website forcefully connects me to Amazon, and OpenStreetMap does just that. Each profile image is stored on Amazon S3, which client browser directly connects to.

OpenStreetMap-NG enhances user privacy by acting as a proxy for Amazon-stored information. Instead of your client browser directly connecting to Amazon S3 for profile images, it connects to the OpenStreetMap server. The server then fetches the requested file from Amazon, caches it locally, and responds to your browser. This approach not only improves privacy but also brings performance benefits by reducing the number of TLS connections established by the client.

## Faster Page Loading

In this release, I've tackled one of the biggest Ruby version bottlenecks - the constant re-rendering of markdown text, which was not very efficient. This issue affected almost everything, including changesets, user profiles, and diaries. The new release intelligently caches the rendered text, resulting in noticeably faster page loading for the majority of pages.

## Security Enhancements and Fixes

OpenStreetMap-NG addresses a range of security concerns while introducing notable enhancements. For instance, administrative accounts now employ computationally expensive password hashes for added security. Future plans include implementing 2FA (Two-Factor Authentication) and U2F (Universal 2nd Factor).

The most significant security vulnerabilities were reported to Ruby security maintainers using a coordinated vulnerability disclosure approach. The timeline for this disclosure is as follows:

- **2023-11-04** - Contacted Ruby security maintainers & disclosed the timeline publicly
- **2024-03-02** - Publicized vulnerability details

The maintainers are given up to 120 days to resolve the issues, but the vulnerability details may be made public earlier if necessary fixes are deployed on OpenStreetMap production servers.

## User Permalinks

Currently, providing reliable user profile links can be challenging due to users' display names being subject to change. OpenStreetMap-NG introduces a new user permalink format, offering a dependable way to link users. Each profile now features a "copy permalink" button.

For instance, while the standard link appears as:

https://www.openstreetmap.org/user/NorthCrab

the user permalink follows this format:

https://www.openstreetmap.org/user/permalink/15215305

Apart from convenience, this change simplifies the development process of various OSM-based tools, as it eliminates the need to store and update the latest user display name information, which is often an unnecessary convenience.

## Identification of Anonymous Note Users

_(Note: This feature is still under consideration. Community consultation will be held before making any final decision.)_

OpenStreetMap-NG proposes a method for identifying anonymous note users through privacy-respecting, unique, and deterministic identicons (random avatars). These identicons are generated based on the user's IP address when a note is created.

Privacy Safeguards:

The identicons are generated using a SHA256 hash formula that combines the user's IP address with an application-specific secret key (INSTANCE_SECRET). This approach ensures that it's impossible to reverse-engineer the user's IP address from the identicon or vice versa, thanks to the inclusion of the secret key in the hash calculation.

The formula behind generating an identicon is:

`SHA256(IP + INSTANCE_SECRET)`

Alternatively, if it's decided that identicons should be unique every year, the formula would be:

`SHA256(IP + NOTE_CREATE_YEAR + INSTANCE_SECRET)`

This feature maintains full backward compatibility with previous versions of the platform. The existing Ruby-based system already collects and stores the IP addresses of anonymous note users, ensuring a seamless transition.

The feature has two main goals. It aims to make it easier to resolve anonymous notes while also ensuring user privacy. The secure and non-reversible identicon generation helps to achieve both these objectives without compromise.

<img src="https://files.monicz.dev/osm/identicon.webp" alt="Three identicons example" height="100px">

## Ability to Rotate OAuth Keys

Currently, the website lacks a convenient method for rotating OAuth private keys without the need to re-register the application. OpenStreetMap-NG addresses this issue by introducing the ability to regenerate private and public keys at any time, simplifying the key management process.

## Deprecation of OAuth 1.0

With this release, OpenStreetMap-NG initiates the deprecation period for OAuth 1.0. The new protocol version, OAuth 2.0, will be used instead. OAuth 2.0 offers significant simplification in integration, management, and performance. The sooner we transition to OAuth 2.0, the better for everyone involved.

### Deprecation Timeline

_(Please note that the following timeline is not final and is subject to change.)_

**Release Date**: When registering an OAuth 1.0 application, a warning is displayed, explaining that new applications should use OAuth 2.0, and OAuth 1.0 functions as a backward compatibility-only feature.

**2024-01**: Only users who previously registered an OAuth 1.0 application can register new OAuth 1.0 applications. For other users, the OAuth 1.0 registration form is disabled. A mass email is sent to users managing OAuth 1.0 applications, notifying them of the deprecation procedure.

**2024-03**: A reminder mass email is sent to users managing OAuth 1.0 applications, which are still actively authenticating users to the API.

**2024-06**: Registration of new OAuth 1.0 applications is disabled for everyone. For all requests authorized using OAuth 1.0, a 200ms delay penalty is issued.

**2025-01**: For all requests authorized using OAuth 1.0, a 500ms delay penalty is issued.

**2025-06**: A final reminder mass email is sent to users managing OAuth 1.0 applications, which still actively authenticate users to the API. For all requests authorized using OAuth 1.0, a 2000ms delay penalty is issued.

**2026-01**: OAuth 1.0 support is disabled.

## Improved GPX Traces

Uploading GPX traces on the Ruby website usually takes tens of seconds, and in some cases, up to a minute of processing. To address this issue, the GPX upload system was made asynchronous, but this further complicated API usage. Moreover, there is no way to check via the API whether a GPX upload was successful or not. The Python version solves this issue by significantly optimizing the GPX processing pipeline, reducing the processing time to just a few seconds. With this change, GPX uploads via the API now provide immediate feedback on the success of the import.

Additionally, the Ruby website attempted to enable anti-aliasing of generated images, but due to the 'P' (palette) image color mode, this was never functional. Anti-aliasing and palette color modes are ideologically incompatible. OpenStreetMap-NG addresses this by switching images to a proper 'L' (grayscale) color mode.

Numerous optimizations to the image generation process now make it possible to generate both the animation and icon in just under 30ms, single-threaded, regardless of the trace point count. The secret sauce for achieving this efficiency is the use of sampling method.

![Side-by-side GPX animation comparison. Left: Ruby version with 15.8 KiB file size. Right: Python version with 11.9 KiB file size and 25ms generation time.](https://files.monicz.dev/osm/gpx-comparison.webp)

You can compare the [Ruby version](https://files.monicz.dev/osm/old_11152535.gif) and [Python version](https://files.monicz.dev/osm/new_11152535.webp) in full screen.

Also, here's a quick comparison of the icon images:

![Ruby version GPX trace icon. Contains hard edges due to non-functional anti-aliasing.](https://files.monicz.dev/osm/old_11152535_icon.gif) vs. ![Python version GPX trace icon. Path edges are smoothed out. Aside of that, it's identical to the Ruby version.](https://files.monicz.dev/osm/new_11152535_icon.webp?cachebuster)

Visualization was performed on trace [#11152535](https://www.openstreetmap.org/user/vjyblauw/traces/11152535).

## Functional sitemap.xml

OpenStreetMap-NG will eventually implement a dynamic sitemap.xml, providing efficient access to website updates for crawlers, including user diaries and profiles. The sitemap includes both new and reputable content, significantly reducing the delay between user-generated content (diaries) and indexing by search engines. The sitemap prioritizes content from trusted users, de-prioritizing or skipping content from new or untrusted users.

## Community Profiles

Introducing community profiles. Now, you can be part of various communities that align with your interests or expertise, and you can also follow communities to stay updated with their activities. Each community profile can showcase its unique identity through customized icons, visible in the members' section of the user profile.

Members within a community, or just the community's moderation team if configured so, can post diaries on the community board. Users following the community will receive notifications of these new posts on their dashboard, ensuring they stay up-to-date with the latest content.

For instance, OSM Poland (OSMP) will have a community profile where verified members of the OSMP organization can be listed. Anyone interested can easily see who belongs to this particular community. Members of the community will have a special badge displayed on their profile, highlighting their affiliation with OSMP.

User profiles will now feature a section where all the communities they belong to are displayed. This enhances the social aspect of OpenStreetMap and provides an easy way for like-minded individuals to connect.

## Migration Plan

OpenStreetMap-NG is designed with a smooth migration process from the ground up. To ensure a seamless transition, I recommend initially deploying the new system on OpenStreetMap's development server. This allows for thorough testing and validation of all migration procedures before they're executed on the production environmen

The primary task for migration involves the database. Backend structures in OpenStreetMap-NG closely resemble those in the original system, often requiring only field renaming for compatibility. Data is transferred from PostgreSQL using simple SQL SELECT statements, processed minimally within a migration script, and then uploaded to MongoDB. Given the similarity in database structures, this data migration step is easy to execute.

No migration is required for the file store (local and S3), further easing the transition process.

## Roadmap

- [x] Architecture design
- [x] Migration of the database models
- [x] Migration of translations
- [x] Migration of various utilities and "lib" folder
- [x] Cache for markdown generated content (faster page loading)
- [x] Migration of OAuth 1.0 & OAuth 2.0
- [80%] Authorization
- [x] Optimistic diff processing
- [80%] Migration of API 0.6
- [x] Improved GPX traces processing
- [ ] Migration of website API
- [ ] Migration of the front-end
- [ ] 🎉 **FEATURE-PARITY POINT** 🎉
- [ ] Anti-vandalism stage 1
- [ ] Deprecation of OAuth 1.0 warning
- [ ] User permalinks
- [25%] Proxy for Amazon requests (better privacy)
- [ ] Addition of Rapid editor
- [ ] Ability to rotate OAuth keys
- [ ] Scheduled account delete
- [ ] Identification of anonymous note users
- [ ] Anti-vandalism stage 2
- [ ] Design finalization of API 0.7
- [10%] Development of API 0.7
- [ ] 2FA and U2F support
- [ ] Community profiles
- [ ] Functional sitemap.xml

**📅 Expected feature parity by:** 2023-12-01

**📅 Expected roadmap finish by:** 2024-02-01

## The Future

Once the roadmap is completed, I will focus on enhancing the overall OSM mapping experience through the following projects. The list is unordered, and I cannot guarantee which project will be worked on first:

- **Relatify 2** - A universal relation editor that also features 24/7 monitoring and easy automatic fixes. This project aims to build upon the experience gained from the original Relatify to further enhance the relation mapping experience. Big Thanks to [Lars Röglin](https://www.linkedin.com/in/lars-roeglin/) for contributing to the concept design process, which brought some fantastic ideas for the new editor.

* **Nominatim 2** - I want to create the best reverse geocoding engine this world has seen. It will be completely free software, and fully based on the OpenStreetMap data. I have some exciting ideas on how to approach it, although I won't spoil anything yet.

* **OSM API 0.7 Python Framework** - In line with efforts to elevate the OpenStreetMap ecosystem, I'll be developing a Python framework tailored for seamless API 0.7 integration. This robust library is designed with asynchronous support and future-proof architecture, serving as a foundation for both current and upcoming OSM projects.

* **Anti-Vandalism Stage 3** - A fully autonomous AI decision engine for detecting and preventing map vandalism in real-time. This engine continuously updates and adapts to various map events. The moderation team can monitor the decision engine in a dedicated dashboard and configure it. The AI is trained on complete OpenStreetMap history, including account blocks issued by the DWG (Data Working Group). Suspected vandals receive an automatic account blockade, with an explanation that their account is under manual review. The moderation team is notified of manual review tasks.

## How Can You Help?

### Talk About It

The most impactful way to support this project for free is by spreading the good word. Positive feedback is incredibly motivating and can turn this project into a reality. Together, we can make the new OSM the best it has ever been.

### Become a Patron

I am now a full-time FOSS developer. Please consider supporting me with a small monthly contribution so I can continue working on what I truly love: OpenStreetMap. I will continue revolutionizing the map with modern, free, and simple solutions. 💪

Support with [Liberapay](https://liberapay.com/Zaczero), [GitHub](https://github.com/sponsors/Zaczero) or [Patreon](https://patreon.com/Zaczero).

Should you have any questions about my work, please feel free to [contact me](https://monicz.dev/#get-in-touch). I'm committed to maintaining full transparency with the community. If a face-to-face discussion is more your style, video chats are also an option.

**Let's do this, together!**

## Thank You Section

A big shoutout to everyone who has supported, motivated, and believed in me throughout this journey. This project wouldn't have been possible without you.

**[OpenStreetMap moderators "DWG"](https://osmfoundation.org/wiki/Data_Working_Group)** - A heartfelt thank you to the entire team for dedicating countless hours to ensuring a safe and respectable environment for all of us. Stay strong, and don't let those vandals win. I deeply appreciate your work. Special thanks to **[Graeme Fitzpatrick "Fizzie41"](https://wiki.openstreetmap.org/wiki/User:Fizzie41)** for being an awesome person, and it's always a pleasure to chat with you.

**[Włodzimierz Bartczak "Cristoffs"](https://www.openstreetmap.org/user/Cristoffs)** - Thank you for supporting me throughout the entire journey. Having someone like you to share enthusiasm with has been truly wonderful. I'm grateful for the countless times we've engaged in discussions, exploring even the craziest of ideas together.

**[Mateusz Konieczny](https://mapsaregreat.com/)** - You provided the spark that lit the fire for this initiative. Thanks for pushing me to bring this project to life.

**[Guillaume Rischard "Stereo"](https://www.openstreetmap.org/user/Stereo)** - Your positive support and respectful approach is truly uplifting. You are the shining example, and I deeply appreciate your kindness.

**[Michał Brzozowski "RicoElectrico"](https://www.openstreetmap.org/user/RicoElectrico)** - A big thank you for your insightful contributions. "OpenStreetMap-NG" is, without a doubt, the perfect name for this project.

**OpenStreetMap vandals 🧌** - Your presence has made this project possible. You are the driving force that keeps me motivated to bring positive change to the world. I also want to express my gratitude for providing the necessary training data for future AI detection models. Rest assured, I will make the most of it. Thank you!
