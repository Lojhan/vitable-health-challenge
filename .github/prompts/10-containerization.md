# 10 Containerization

You are an expert full-stack engineer. We are building a Healthcare AI Chatbot POC with containerization support.

## The Vision

Ship the application in reproducible, isolated containers for consistent deployment across development, staging, and production environments. Container images are built using Docker/Podman with multi-stage builds for efficiency.

## The Rules of Engagement

- All Dockerfiles use multi-stage builds to minimize image size
- Container images are tagged with semantic versioning when released
- docker-compose.yml orchestrates all services including PostgreSQL for development
- Non-root users run containers for security
- Environment variables are externalized and documented
- .dockerignore excludes unnecessary files to reduce build context
- All images build successfully with `docker build` or `podman build`
- Application tests pass within containerized environment
- You MUST NOT modify Dockerfile CMD/ENTRYPOINT without explicit request

## Components

### Backend Container
- Base image: `python:3.11-slim` for minimal footprint
- Multi-stage build separates dependencies from runtime
- Exposes port 8000 for Django development/ASGI server
- Runs as non-root user (appuser, uid 1000)
- Environment variables: DJANGO_SETTINGS_MODULE, OPENROUTER_API_KEY, DATABASE_URL

### Frontend Container
- Base image: `node:20-alpine` for minimal footprint
- Multi-stage build separates build from serve
- Builds with `npm run build` producing optimized dist/
- Serves with `serve` package on port 3000
- Runs as non-root user (appuser, uid 1000)
- Minimal runtime dependencies only

### Docker Compose
- Orchestrates backend, frontend, and PostgreSQL services
- Postgres uses alpine variant, port 5432
- Health checks ensure service dependencies
- Volume mounts for development (code reload)
- Environment variable injection for OpenRouter API key
- Named volume `postgres_data` for data persistence

## Tasks for this Prompt

1. **Build and test the backend image:**
   - Run `docker build -t vitable-backend:latest ./backend`
   - Verify image builds successfully
   - Confirm image runs with `docker run -p 8000:8000 vitable-backend:latest`

2. **Build and test the frontend image:**
   - Run `docker build -t vitable-frontend:latest ./frontend`
   - Verify image builds successfully
   - Confirm image runs with `docker run -p 3000:3000 vitable-frontend:latest`

3. **Test docker-compose orchestration:**
   - Set OPENROUTER_API_KEY in environment: `export OPENROUTER_API_KEY=sk-or-v1-...`
   - Run `docker-compose up` to start all services
   - Verify all services start without errors
   - Check that backend is accessible at http://localhost:8000
   - Check that frontend is accessible at http://localhost:3000
   - Run `docker-compose down` to stop services

4. **Document container usage:**
   - Add container usage instructions to root README.md
   - Include commands for building, running, and stopping containers
   - Document environment variables required for both containers

## Memory Check

When you complete this prompt, provide a Memory Check that:
- Lists all Docker/Podman images successfully built
- Confirms docker-compose orchestration works
- States all services start and communicate correctly
- Notes any modifications to build processes or dependencies
- Confirms README.md documentation was added
- Declare you are standing by for the next task
