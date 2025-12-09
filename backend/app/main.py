#E:\HOPEAI\PJT\genai_translation\backend\app\main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import translate_router
from fastapi.staticfiles import StaticFiles
from app.ai_engine.generate_workflow_png import generate_workflow_png
from contextlib import asynccontextmanager
import uvicorn

# --------------------------------------------------
# LIFESPAN HANDLER (Modern FastAPI startup method)
# --------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    try:
        generate_workflow_png()
        print("Workflow diagram regenerated successfully (lifespan).")
    except Exception as e:
        print("Failed to generate workflow diagram:", e)

    yield  # application runs here

    # Shutdown logic (not needed here)
    print("Shutting down…")

# --------------------------------------------------
# APP INITIALIZATION
# --------------------------------------------------
app = FastAPI(
    title='Translation API (MVC)',
    docs_url=None,        # disable default /docs
    redoc_url=None,        # disable default /redoc
    lifespan=lifespan
)

#app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# ---------- CORS ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# ---------- ROUTER ----------
app.include_router(translate_router.router, prefix='/api', tags=['translation'])

@app.get('/health/ping')
def ping():
    return {'ok': True}

if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8000)
