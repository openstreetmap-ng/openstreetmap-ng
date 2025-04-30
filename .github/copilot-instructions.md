# OpenStreetMap-NG

- **Vision:**
Establish OpenStreetMap-NG as the definitive next-generation open mapping platform.

- **Mission:**
Empower global communities by building the most innovative, user-centric, and performant open mapping service.

## Core Objectives

- **Innovation:**
Continuously deliver impactful new features and capabilities.

- **User Experience:**
Prioritize intuitive interfaces and seamless interactions through modern design practices.

- **Performance:**
Engineer for speed and reliability across diverse devices and network conditions.

## Technology Stack

- **Backend:**
Python 3.13+ leveraging `asyncio` with FastAPI for high-throughput, modern asynchronous services.

- **Frontend:**
Jinja2 for server-side templating, vanilla TypeScript for efficient client-side logic, and Bootstrap SCSS for standardized, maintainable styling.

- **Localization:**
New translations are stored in the config/locale/extra_en.yaml file, following the i18next JSON v4 format. They are automatically available to both the frontend and backend.

## Development Principles

- **Code Quality:**
Write clear, simple, and robust code. Aim for low cyclomatic complexity and favor linear control flow to create lean, effective solutions built for long-term viability and ease of maintenance.

- **Modern Practices:**
Utilize modern language features (Python 3.13+, ESNext) and embrace asynchronous patterns for optimal resource utilization.

- **Dependency Strategy:**
  - Implement simple or project-specific logic directly to maintain control and minimize the external dependency footprint.
  - Integrate well-vetted, high-performance external packages (like `httpx`, `numpy`, `duckdb` where applicable) for complex, standardized tasks to enhance robustness, reduce bugs, and lower maintenance effort.
