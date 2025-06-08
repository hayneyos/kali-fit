import os
import sys

from backend.app_recipe.utils.logger import LoggerConfig, get_logger

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, project_root)

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from dotenv import load_dotenv
import uvicorn
from backend.app_recipe.routes.v1.mock.mock_model_routes import router as mock_model_router


from backend.app_recipe.routes.v1.outer_poc.revenuecat_routes import router as revenuecat_router
from backend.app_recipe.routes.v1.outer_poc.rtdn_routes import router as rtdb_router
from backend.app_recipe.routes.v1.outer_poc.influencer_routes  import router as influencer_router

from backend.app_recipe.routes.v1.prod.wizard_routes import  router as wizard_router
from backend.app_recipe.routes.v1.prod.meals_routes import router as meals_router
from backend.app_recipe.routes.v1.prod.model_routes import router as model_router
from backend.app_recipe.routes.v1.prod.recipe_routes import router as recipe_router
from backend.app_recipe.routes.v1.prod.common_routes import router as common_router
from backend.app_recipe.routes.v1.prod.fit_routes import router as fit_router


# Configure logger
logger_config = LoggerConfig(
    log_dir="logs",
    log_level=logging.INFO,
    console_output=True
)
logger = get_logger('app', level=logging.INFO)

logger.info("🔍 Before dotenv load:")
logger.info(f"DATA_DIR = {os.getenv('DATA_DIR')}")

# Explicitly load .env file
env_path = os.path.join(os.path.dirname(__file__), ".env")
logger.info(f"Loading .env from: {env_path}")
load_dotenv(dotenv_path=env_path)

logger.info("✅ After dotenv load:")
logger.info(f"DATA_DIR = {os.getenv('DATA_DIR')}")

# Global startup state
is_startup_complete = False

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global is_startup_complete
    is_startup_complete = False
    logger.info('Start loading data')
    try:
        # await init_data2()
        is_startup_complete = True
        logger.info('Finish loading data')
        yield
    except Exception as e:
        logger.error(f'Error during startup: {str(e)}')
        is_startup_complete = False
        raise e
    finally:
        # Shutdown
        logger.info('Shutting down')
        is_startup_complete = False

app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

# Configure static files
if os.getenv("RUNNING_IN_DOCKER") == "true":
    static_path = "/usr/src/backend/app/static"
else:
    static_path = os.path.join(os.path.dirname(__file__), "static")

# Create static directory if it doesn't exist
os.makedirs(static_path, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_path), name="static")

# Configure CORS
origins = [
    f"http://{os.getenv('MY_SERVER_IP')}:8082",
    f"http://{os.getenv('MY_SERVER_IP')}:8093",
    f"http://{os.getenv('MY_SERVER_IP')}:8094",
    f"https://www.{os.getenv('MY_SERVER_NAME')}",
    f"https://{os.getenv('MY_SERVER_NAME')}"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or only your domain for security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

USE_API_PREFIX = os.getenv("USE_API_PREFIX", "false").lower() == "true"
logger.info(f"Allowed origins: {origins}")

# Add rate limit middleware
# rate_limit_middleware = RateLimitMiddleware(app)
# app.add_middleware(rate_limit_middleware.__class__)
app.include_router(model_router)
app.include_router(mock_model_router)

app.include_router(recipe_router)
app.include_router(revenuecat_router)
app.include_router(common_router)


app.include_router(rtdb_router)
app.include_router(influencer_router)
app.include_router(meals_router)

app.include_router(wizard_router)

app.include_router(fit_router)





@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    """Handles HTTP exceptions and returns JSON response."""
    logger.error(f"HTTP Exception: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail or "An error occurred"},
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handles generic exceptions and returns a JSON response."""
    logger.error(f"Unhandled Exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error", "detail": str(exc)},
    )

@app.get("/")
@app.get("/health")
async def health_check():
    """Health check endpoint for Docker container."""
    if not is_startup_complete:
        logger.warning("Health check failed: Application is still initializing")
        return JSONResponse(
            status_code=503,
            content={
                "status": "initializing",
                "message": "Application is still initializing"
            }
        )
    logger.info("Health check passed: Application is healthy")
    return {"status": "healthy"}

@app.options("/handle_event")
async def handle_event_options():
    """Handle OPTIONS requests for the old /handle_event endpoint"""
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "86400"
        }
    )

if __name__ == "__main__":
    # if os.getenv("ENV", "dev") == "dev":
    # os.system("uvicorn main:app --host 0.0.0.0 --port 8091 --reload")
    # else:
        uvicorn.run(
            "main:app",
            host=os.getenv('SERVER_HOST', '0.0.0.0'),
            port=int(os.getenv('SERVER_PORT', 8091)),
            loop="uvloop",
            limit_concurrency=1000,
            backlog=2048,
            workers=1,
            reload=True,  # Enables hot reload (use only in development)
            log_level="debug"
        )