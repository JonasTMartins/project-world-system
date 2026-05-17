from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"message": "World system is running"}