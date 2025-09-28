from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from auth.router import router as auth_router
from claims.router import router as claims_router
from health.router import router as health_router
from upload.router import router as upload_router
from audit.router import router as audit_router
from validation.router import router as validation_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Starting up the application...")
    yield
    # Shutdown
    print("Shutting down the application...")


app = FastAPI(
    title="RCM Validation Engine API",
    description="API for validating and managing revenue cycle management claims. "
    "Provides endpoints for authentication, claim CRUD operations, "
    "and health checks.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(claims_router)
app.include_router(health_router)
app.include_router(upload_router)
app.include_router(audit_router)
app.include_router(validation_router)


@app.get("/")
def read_root():
    return {"message": "Welcome to RCM Validation Engine API"}
