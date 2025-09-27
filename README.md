# Backend - RCM Validation Engine

This is the FastAPI backend for the RCM Validation Engine.

## Setup

1. Ensure Python 3.10+ is installed.
2. Create virtual environment: `python -m venv venv`
3. Activate: `source venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Copy `.env.example` to `.env` and configure variables.
6. Run migrations: `alembic upgrade head`
7. Start server: `uvicorn main:app --reload --port $PORT`

## Environment Variables

- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `SECRET_KEY`: JWT secret
- `OPENAI_API_KEY`: OpenAI API key
- `PORT`: Server port (default 8000)
- Other configs as in `.env`

## API Endpoints

- `/api/v1/auth/token`: POST - Login
- `/api/v1/claims/`: GET/POST - List/Create claims
- `/api/v1/claims/{id}`: GET/PUT/DELETE - Claim operations
- `/api/v1/health/`: GET - Health check

## Docs

- Swagger: `/docs`
- ReDoc: `/redoc`
