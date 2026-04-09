# Vitable Health Challenge

A full-stack healthcare AI triage chatbot. Patients describe symptoms in a chat interface; the AI nurse triages them using the Manchester Triage System, can call scheduling tools, and flags life-threatening emergencies automatically.

---

## Stack

| Layer | Technology |
|---|---|
| Backend | Django 6.0.4, Python 3.13 |
| API framework | django-ninja 1.6.2 (OpenAPI) |
| Auth | django-ninja-jwt 5.4.4 (JWT) |
| AI | OpenRouter via `openai` SDK |
| Database | PostgreSQL |
| Frontend | Vue 3, Vite 5, Pinia, PrimeVue 4 (Aura) |

---

## Prerequisites

- Python 3.13
- Node.js 20+
- PostgreSQL (running locally or via a connection string)
- An [OpenRouter](https://openrouter.ai) API key

---

## Backend setup

### 1. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

### 2. Install dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 3. Configure environment

Create a `.env` file in the `backend/` directory (next to `manage.py`):

```env
POSTGRES_DB=chatbot_db
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

OPENROUTER_API_KEY=sk-or-v1-...
```

> If `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_HOST` are omitted, Django falls back to the current OS user and a local socket connection.

### 4. Create the database

```bash
psql -U postgres -c "CREATE DATABASE chatbot_db;"
```

### 5. Run migrations

```bash
python manage.py migrate
```

### 6. Create a superuser (optional)

```bash
python manage.py createsuperuser
```

### 7. Start the development server

```bash
python manage.py runserver
```

The API is available at `http://localhost:8000/api/`. Interactive docs: `http://localhost:8000/api/docs`.

---

## Running backend tests

```bash
# from the backend/ directory, with the venv active
pytest -q
```

All tests are in `chatbot/features/*/tests.py` and `chatbot/features/*/test_*.py`. The test suite uses `pytest-django` with the `@pytest.mark.django_db` marker.

---

## Frontend setup

```bash
cd frontend
npm install
npm run dev      # dev server at http://localhost:5173
npm run build    # production build → dist/
npm test         # Vitest unit tests
```

---

## Project structure

```
backend/
├── manage.py
├── requirements.txt
├── pytest.ini
├── backend/              # Django project settings & urls
└── chatbot/
    └── features/
        ├── users/        # Custom User model + auth endpoints (token, signup)
        ├── ai/           # BaseAgentInterface + OpenRouterAgent
        ├── billing/      # Insurance tier pricing logic
        └── scheduling/   # Appointment model + RRULE scheduling tools

frontend/
├── src/
│   ├── views/            # Login.vue, Signup.vue
│   ├── components/       # ChatInterface.vue + tests
│   ├── stores/           # auth.js (Pinia), chat.js (Pinia)
│   └── lib/              # apiClient.js (Axios + JWT interceptor)
└── vite.config.js
```

---

## Docker / Podman

Build and run the application in containers for consistent environments across development and production.

### Prerequisites

- Docker or Podman installed
- OpenRouter API key set as environment variable

### Build images

```bash
# Build backend image
docker build -t vitable-backend:latest ./backend

# Build frontend image
docker build -t vitable-frontend:latest ./frontend
```

### Run with docker-compose

```bash
# Set the OpenRouter API key
export OPENROUTER_API_KEY=sk-or-v1-...

# Start all services (PostgreSQL, backend, frontend)
docker-compose up

# Stop all services
docker-compose down
```

Services will be available at:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000/api/
- **PostgreSQL**: localhost:5432

### Run individual containers

```bash
# Run backend only (requires external PostgreSQL)
docker run -p 8000:8000 \
  -e OPENROUTER_API_KEY=sk-or-v1-... \
  vitable-backend:latest

# Run frontend only
docker run -p 3000:3000 vitable-frontend:latest
```

### Using Podman

Replace `docker` with `podman` in all commands above. The Dockerfiles and docker-compose.yml are fully compatible with Podman:

```bash
podman build -t vitable-backend:latest ./backend
podman build -t vitable-frontend:latest ./frontend
podman-compose up
```
