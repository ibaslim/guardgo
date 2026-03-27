from pydantic import BaseModel


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPassword(BaseModel):
    token: str
    password: str


class InviteActivationRequest(BaseModel):
    token: str
    password: str
    username: str
    full_name: str
