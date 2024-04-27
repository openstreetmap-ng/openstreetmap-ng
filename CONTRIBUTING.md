# All-in-One Contributor Guide

Welcome to the project and thank you for your interest in contributing! This guide will help you get started with the project and provide you with the necessary information to make your first contribution.

### 1️. Required Software

OpenStreetMap-NG focuses on simplicity. We use a minimal set of tools to keep the development process straightforward, secure, and easy to understand. The development environment is automatically configured with Nix, and this is the only tool you need to install yourself.

- Nix — [Installation instructions](https://nixos.org/download/)

### 2. Starting the Development Environment

After you have installed Nix, and obtained the project source code, you can enter the development environment by running the following command inside the project directory:

```sh
nix-shell
```

> [!TIP]
> You can automate the `nix-shell` step, by installing an optional [direnv](https://direnv.net) program. We already provide a `.envrc` configuration file that will automatically enter the development shell when you enter the project directory.

Once you are inside the development shell, you can start your favorite text editor from within it. This ensures that your IDE will have access to the same environment:

```sh
# Visual Studio Code:
code .
# PyCharm:
charm .
```

### 3. Starting the Services

During a typical development session, you will most likely need to start the project services, such as the PostgreSQL database. When you are inside the development shell, we provide you with a set of scripts to do just that. The following command will start all necessary services and run the database migrations:

```sh
dev-start
```

> [!TIP]
> All custom scripts are defined in the `shell.nix` file. Other useful scripts include `dev-stop` to stop the services, and `dev-clean` to clean services data files.

### 4. Preloading the Database (Optional)

For some development tasks, you might want to preload the database with some real-world OpenStreetMap data. We make this process easy by providing a script that does everything for you:

```sh
dev-clean  # Clean the database first (recommended)
preload-pipeline
```

The download size is about 4 GB, and the result is cached on your local machine in `data/preload` directory. Subsequent preloads will be able to reuse the cache.

The import process takes around 30-60 minutes.

### 5. Project Structure

It's now a good time to familiarize yourself with the project structure. Here is what you should know:

- **app**: Main application code
- **app/alembic**: Database migrations
- **app/controllers**: HTTP request handlers
- **app/exceptions**: Exception helpers
- **app/format**: Data formatting helpers
- **app/lib**: General-purpose classes
- **app/middleware**: HTTP request middlewares
- **app/models**: Models
- **app/models/db**: Database models
- **app/repositories**: Database read-only queries
- **app/services**: Database business logic
- **app/static**: Static web assets
- **app/templates**: HTTP response templates
- **config**: Configuration files
- **scripts**: Python scripts (used in `shell.nix`)
- **tests**: Test suite
