from pydantic import BaseModel


class ModelLogin(BaseModel):
    username: str
    password: str


class ModelRegister(BaseModel):
    email: str
    username: str
    password: str


class ModelDetector(BaseModel):
    owner: str


class ModelAddDetector(BaseModel):
    cam_source: str
    nickname: str


class ModelCam2Events(BaseModel):
    cam_source: str


class ModelGetEventFrames(BaseModel):
    event_name: str


class ModelDelEvent(BaseModel):
    event_name: str
    cam_source: str

class ModelGetNotification(BaseModel):
    cam_source: str

class ModelAuthentication(BaseModel):
    ip: str
    user: str
    password: str
    path: str
    protocol: str
    id: str
    action: str
    query: str
