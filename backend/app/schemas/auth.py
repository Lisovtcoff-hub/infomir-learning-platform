from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SessionCreated(BaseModel):
    ok: bool = True
