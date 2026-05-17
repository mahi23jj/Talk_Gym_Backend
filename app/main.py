from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.services.Ai_Transaltion import _get_model



app = FastAPI(title=settings.app_name, version=settings.app_version)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    _get_model()



app.include_router(api_router)



@app.get("/", tags=["Root"])
def root() -> dict[str, str]:
    return {"message": f"{settings.app_name} is running"}
