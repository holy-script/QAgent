from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from qagent.api.routes import dev, apps, runs, playbooks, health, artifacts

app = FastAPI(
    title="QAgent API",
    description="Backend API for QAgent autonomous web application QA platform",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dev.router)
app.include_router(apps.router)
app.include_router(runs.router)
app.include_router(playbooks.router)
app.include_router(health.router)
app.include_router(artifacts.router)


@app.get("/")
async def root():
    return {
        "service": "QAgent API",
        "version": "0.1.0",
        "docs": "/docs",
        "openapi": "/openapi.json",
    }
