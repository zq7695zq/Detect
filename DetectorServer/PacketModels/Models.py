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
    page: int


class ModelGetEventFrames(BaseModel):
    event_name: str


class ModelDelEvent(BaseModel):
    event_name: str
    cam_source: str


class ModelAddReminder(BaseModel):
    cam_source: str
    frame: str
    rect: list
    select_time: str
    reminder_name: str
    reminder_type: int


class ModelIsRecording(BaseModel):
    cam_source: str


class ModelGetNotification(BaseModel):
    cam_source: str


class ModelGetRecords(BaseModel):
    cam_source: str

class ModelGetWav(BaseModel):
    cam_source: str
    file: str

class ModelAddVoice(BaseModel):
    cam_source: str
    file: str
    label: str