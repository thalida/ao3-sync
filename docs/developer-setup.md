# Developer Setup

## Recommended: VSCode Dev Container

This project is configured to work with the [VSCode Dev Container](https://code.visualstudio.com/docs/remote/containers) extension. This extension allows you to develop in a containerized environment that is consistent with the production environment. This is the recommended way to develop this project.

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- [VSCode](https://code.visualstudio.com/)

### Setup

1. Clone the repository
2. Open the repository in VSCode
3. VSCode will prompt you to reopen the repository in a container. Click "Reopen in Container"
4. The container will build and open in a new VSCode window
5. Open a terminal in the new VSCode window
6. Begin developing!

## How To: Serve Documentation

```bash
mkdocs serve --watch .
```

Visit [http://localhost:8000](http://localhost:8000) in your browser to view the documentation.
