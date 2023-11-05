Here I answer questions asked by the community.

## Introduction

### What does it mean for an average map user? ([src](https://community.openstreetmap.org/t/the-next-generation-of-openstreetmap-in-python/105621/7))

As OpenStreetMap becomes more developer-friendly, average users can anticipate an increase in the quality and quantity of applications based on OSM. Furthermore, enhancements, changes, and fixes on the OpenStreetMap.org website will be streamlined. In essence, the overall OSM experience will see improvement.

## Community

### Have you been in contact with the contributors to the current code before this announcement? ([src](https://community.openstreetmap.org/t/the-next-generation-of-openstreetmap-in-python/105621/2))

Considering both code contributors and operational members managing the infrastructure, the answer is largely no. I understand the hesitancy in trusting new contributors for significant changes. Thus, I chose to make substantial progress first before initiating open discussions. With the evidence of the project's advancement, these conversations can now take place.

### In general suspect that improving existing codebase would be much better than (...) everything at once. ([src](https://community.openstreetmap.org/t/the-next-generation-of-openstreetmap-in-python/105621/4))

The current code base is incredibly convoluted to work on. Personally, I see the "everything at once" switch as the only viable option to move forward. Ruby needs to go, and if we are at the point of completely switching programming languages, there is very little left to the "everything at once" stage, so we may as well go with it. I am fully committed to providing a stable, easy-migratable solution that "just works." As the project matures, I will provide enough evidence to leave no doubt about the reliability of the new solution.

### Trying to come out of nowhere with a huge revamp of an existing system. And I’ve seen plenty of others do similar things. The results were always the same. ([src](https://community.openstreetmap.org/t/the-next-generation-of-openstreetmap-in-python/105621/5))

This project is and has been my full-time commitment. I am all in.

## Technical

### What is the technical reason for mowing away from PostgreSQL/PostGIS? I do not see an objective benefit that does outweight the work involved in migrating the database engine. ([src](https://community.openstreetmap.org/t/the-next-generation-of-openstreetmap-in-python/105621/2))

I'll start with a short talk about my development style. I have always loved developing software, but for the majority of the time, I never really understood what exactly I loved so much about it. As I slowly transitioned to Python, something finally clicked. I don't care about micromanagement, I don't care about micro-optimizations; what I care about is having fun, exploring new ideas, and being flexible. I treat a piece of code like a fun puzzle to play with. Just as I fell in love with Python, I also fell in love with schema-less databases. Schema-less databases are fun to work on, making it easy to explore new ideas, innovate, and remain super flexible. I've finally found the perfect combination for creating fun software: Python + NoSQL.

The reason I don't find joy in SQL is the same reason I don't find joy in low-level languages like C++ or Rust. They all focus on matters that are not developer-centric but rather computer-centric. I fully understand and accept that there are valid reasons for using SQL (and C++/Rust) and that without them, we wouldn't be here. However, for the software I create, I don't find enough justification to force myself to use a schema-based design when it can run just as well without it, reducing many complexities in the code and being more friendly to newcomers.

With SQL, you have to know various abstract concepts like normalization and migration, but with NoSQL, you don't! With document databases, you simply work on a collection of JSON-like files. For these reasons, I want OSM-NG to move away from SQL to make it easy for anybody to contribute to the project.

To answer the second part of the question, the project is designed from the ground up with an easy migration process in mind. Database migration is the easy part in all of this! I value the time of others, and I will make sure that the transition is as smooth as possible.

### What are written considerations about the chosen tech stack? ([src](https://community.openstreetmap.org/t/the-next-generation-of-openstreetmap-in-python/105621/3))

In this answer, I will skip talk about Python as it's obvious, and MongoDB as it has been answered in another question. Instead, I'll focus on the fundamental packages used by the project: FastAPI (web server) and Pydantic (data models).

When choosing the web server, I considered FastAPI, Flask, and Django. Django's async support is preliminary and, for that reason, it's immediately ruled out. Now, when deciding between FastAPI and Flask, FastAPI emerged as the preferred choice for several reasons:

1. FastAPI is built from the ground up with async support in mind, and all its documentation emphasizes async code usage.
2. FastAPI leverages modern Python features like Annotated[] that enhance code readability and extensibility.
3. FastAPI operates under the hood with Pydantic, providing a 2-in-1 solution.

Speaking of Pydantic, when compared to dataclasses and attrs, it seems like an obvious choice for this use case:

1. Pydantic offers extensive validation features, simplifying the safeguarding against potential format errors and corruptions.
2. It enables the code to perform format transformations, such as converting shapely Geometry objects to GeoJSON (utilized by MongoDB) and vice versa, by creating small serializers and validators.
3. Pydantic provides a way to construct models without validation logic for efficient mass-data retrievals.

These considerations make FastAPI and Pydantic a perfect combination for this project.

### Will there initially be backwards compability with API 0.6 clients? ([src](https://community.openstreetmap.org/t/the-next-generation-of-openstreetmap-in-python/105621/2))

Yes, /api/0.6/ will work without any notable changes. When /api/0.7/ is released, both versions will be able to operate concurrently, and changes made in one version are compatible with the other.

### Have you stress tested and compared performance of existing SQL setup with your MongoDB idea? ([src](https://community.openstreetmap.org/t/the-next-generation-of-openstreetmap-in-python/105621/4))

I will the moment when the application is operational. It still requires a few weeks of work to reach that stage (see roadmap). I do not expect any surprises; I anticipate the application to run as fast, if not faster, compared to the current release.

### Does your code include an OAuth2 server, or will that be using an off-the-shelf solution liky Keycloak or Ory? ([src](https://community.openstreetmap.org/t/the-next-generation-of-openstreetmap-in-python/105621/2))

The code includes OAuth 1.0 and OAuth 2.0 servers, just like in the Ruby release. When developing the OAuth solution, I explored various Python packages and external OAuth providers. My primary focus was on a solution that included OAuth 1.0 support, as this specification is notably more complex.

The most reasonable ready-made solution I found was the oauthlib package, but since it does not support async, it was a deal-breaker for me. In the end, I decided to implement OAuth 1.0 and OAuth 2.0 endpoints from scratch, using authlib to handle more challenging operations, such as computing OAuth 1.0 signatures. This allowed me to seamlessly integrate the OAuth servers into the application workflow while fully leveraging async features and maintaining flexibility.

The final solution is straightforward to understand and easy to extend if the need comes, while also requiring minimal migration efforts.

### Security is really, really hard to do well, (...). Instead, it would make sense to extract it into some other existing components, like Keycloak or Ory. ([src](https://community.openstreetmap.org/t/the-next-generation-of-openstreetmap-in-python/105621/5))

OSM's OAuth requirements are currently quite limited in scope. While I considered using external authorization components, I found those solutions to be somewhat bulky, and the amount of code required to handle external interactions would be similar in size to the currently prepared OAuth server solution. It would also introduce new challenges and complexities. Simplifying the project's complexities leads to easier maintenance.

Additionally, since the current Ruby release also handles OAuth internally, this reimplementation makes it straightforward to migrate to. As of now, the OAuth specification needs are so minimal that I don't see switching to external providers as a viable option. If OSM's OAuth requirements expand in the future, I am open to supporting such a migration. It will be less of a headache once we have completed this significant initial step.

### Are you aware of the API 0.7 wiki page, which collects suggestions for a new version of the API? Which, if any, of those suggestions have you incorporated? ([src](https://community.openstreetmap.org/t/the-next-generation-of-openstreetmap-in-python/105621/2))

Yes, I am. When considering the fundamentals of API 0.7, I briefly went through it, and I plan to thoroughly read it during the API 0.7 design stage. By that time, I hope to have a suitable place for discussing API 0.7 with the community, which I believe is crucial when developing such an important milestone. Currently, my focus is on achieving feature parity with the current OpenStreetMap website. Once that is accomplished, I will shift my attention to working on the new features.

### I don’t know where in the current API C++ is used, but that’s a language that’s rarely used without a good reason. Have you done some benchmarking of the two APIs to ensure that yours does not introduce a performance regression? ([src](https://community.openstreetmap.org/t/the-next-generation-of-openstreetmap-in-python/105621/2))

The use of C++ can be observed in the cgimap project, which serves as a C++ mirror version of the API 0.6 Ruby code. As far as I know, C++ was chosen due to performance issues and memory leaks found in the Ruby application.

However, I personally didn't find sufficient justification to continue supporting C++. Most of the time, it simply waits for database queries. The most significant time savings come from constructing the API responses (XML encoding). This optimization likely saves a few milliseconds at best per call, which I consider to be in the realm of micro-optimization. Cgimap doesn't perform any computationally expensive operations itself, making it seem like a bad tool for the job.

### I do think that the code structure could use some work, it seems that most of the retrieving logic is housed in the models. ([src](https://community.openstreetmap.org/t/the-next-generation-of-openstreetmap-in-python/105621/3))

The retrieval logic is stored alongside models to create a central location for code responsible for database-related operations, including objects stored in the database. My rationale is that when I create a user with `User(name="test").create()`, it's logical to retrieve that user with `User.find_one_by_name("test")`. While I acknowledge that this approach may not be formally correct, I believe it's straightforward and easy for everyone involved to understand.

I'm open to feedback and considerations on this matter. If you have suggestions on how things should be improved, please feel free to share them, and I'll be happy to discuss and consider them in detail.

### MongoDB is not open-source. ([src](https://community.openstreetmap.org/t/the-next-generation-of-openstreetmap-in-python/105621/4))

The MongoDB Community Edition is source-open and published under the Server-Side Public License (SSPL). This license is derived from the GPL but includes additional terms that mainly impact projects offering MongoDB as a service. However, these additional terms are beyond the scope of OSM operations.

For our purposes, MongoDB can be treated as a GPL-licensed database. This does not affect any of the free and open aspects of the OpenStreetMap-NG project, which continues to remain free and open-source.
