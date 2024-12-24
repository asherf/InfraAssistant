from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from chainlit.utils import mount_chainlit

app = FastAPI()


_CHAINLIT_PATH = "/cl"

@app.get("/app")
def read_main():
    return {"message": "Hello World from main app"}

@app.get("/")
def redirect_to_cl():
    return RedirectResponse(url=_CHAINLIT_PATH)



app.mount("/icons", StaticFiles(directory="assets/public/icons"), name="icons")
mount_chainlit(app=app, target="src/core.py", path=_CHAINLIT_PATH)
