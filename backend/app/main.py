from fastapi import FastAPI

from backend.app.auth.router import router as auth_router

app = FastAPI()

app.include_router(auth_router)

@app.get("/")
def root():
    return {
        "message": "PolicyGPT Backend is running"
    }