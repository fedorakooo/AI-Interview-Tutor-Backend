from typing import Annotated

from fastapi import Depends
from starlette.requests import HTTPConnection

from src.app.container import AppContainer


def get_container(connection: HTTPConnection) -> AppContainer:
    return connection.app.state.container


ContainerDep = Annotated[AppContainer, Depends(get_container)]
