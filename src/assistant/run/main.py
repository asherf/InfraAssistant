from chainlit.utils import mount_chainlit
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from assistant.run import core as assistant_core

app = FastAPI()


_CHAINLIT_PATH = "/cl"


@app.get("/app")
def read_main():
    return {"message": "Hello World from main app"}


@app.get("/")
def redirect_to_cl():
    return RedirectResponse(url=_CHAINLIT_PATH)


app.mount("/icons", StaticFiles(directory="assets/public/icons"), name="icons")
mount_chainlit(app=app, target=assistant_core.__file__, path=_CHAINLIT_PATH)
