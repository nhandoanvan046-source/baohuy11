from fastapi import FastAPI
from threading import Thread
import uvicorn

app = FastAPI()

@app.get("/")
def home():
    return {"status": "Bot is alive!"}

def run():
    uvicorn.run(app, host="0.0.0.0", port=10000)

def keep_alive():
    thread = Thread(target=run)
    thread.daemon = True
    thread.start()
