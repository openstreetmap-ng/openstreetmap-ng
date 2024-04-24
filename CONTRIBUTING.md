# All-in-One Contributor Guide

Welcome to the project and thank you for your interest in contributing! This guide will help you get started with the project and provide you with the necessary information to make your first contribution.

## 1️. Required Software

OpenStreetMap-NG focuses on simplicity. We use a minimal set of tools to keep the development process straightforward, secure, and easy to understand. The development environment is automatically configured with Nix, and this is the only tool you need to install yourself.

- Nix — [Installation instructions](https://nixos.org/download/)

## 2. Starting the Development Environment

After you have installed Nix, and obtained the project source code, you can enter the development environment by running the following command inside the project directory:

```sh
nix-shell
```

> [!TIP]
> You can automate the `nix-shell` step, by installing an optional [direnv](https://direnv.net) program. We already provide a `.envrc` configuration file that will automatically enter the development shell when you enter the project directory.

## 3. Starting the Services

...
