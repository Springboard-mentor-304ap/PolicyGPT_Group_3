from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {
        "message" : "PolicyGPT Backend is running"
    }