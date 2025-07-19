from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.get("/")
def ping():
    return {"status": "bot is huy"}

def keep_alive():
    uvicorn.run(app, host="0.0.0.0", port=10000)
