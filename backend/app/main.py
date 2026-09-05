from fastapi import FastAPI

from backend.app.auth.router import router as auth_router
from backend.app.role_requests.router import router as role_requests_router
from backend.app.profile.router import router as profile_router


app = FastAPI()


app.include_router(auth_router)
app.include_router(role_requests_router)
app.include_router(profile_router)


@app.get("/")
def root():
    return {
        "message": "PolicyGPT Backend is running"
    }
