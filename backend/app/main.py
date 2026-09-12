from fastapi import FastAPI

from backend.app.auth.router import router as auth_router
from backend.app.role_requests.router import router as role_requests_router
from backend.app.profile.router import router as profile_router
from backend.app.eligibility.router import router as eligibility_router
from backend.app.search.router import router as search_router
from backend.app.comparison.router import router as comparison_router
from backend.app.policies.router import router as policy_router
from backend.app.schemes.router import router as scheme_router

app = FastAPI()


app.include_router(auth_router)
app.include_router(role_requests_router)
app.include_router(profile_router)
app.include_router(eligibility_router)
app.include_router(search_router)
app.include_router(comparison_router)
app.include_router(policy_router)
app.include_router(scheme_router)

@app.get("/")
def root():
    return {
        "message": "PolicyGPT Backend is running"
    }
