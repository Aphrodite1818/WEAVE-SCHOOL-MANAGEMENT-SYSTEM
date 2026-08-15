#==========================#
#cbt/auth/schemas.py
#==========================#


"""This file is responsible for schema definition for server authentication request and response"""

from typing import Literal
from uuid import UUID
from pydantic import BaseModel , ConfigDict , EmailStr , Field
from resend import Emails

from app.modules.cbt.enums import CBTServerStatus



class AuthenticatedCBTServer(BaseModel):
    """
    Trusted machine context produced after a CBT server credential
    has been successfully authenticated 

    Routes should use this context instead of accepting tenant_id or
    server_id from the local CBT runtime
    """


    model_config = ConfigDict(
        frozen = True
    )


    server_id : UUID
    tenant_id : UUID
    server_name : str
    status : CBTServerStatus





class CBTStaffLoginRequest(BaseModel):
    model_config = ConfigDict(
        extra = "forbid",
        str_strip_whitespace=True
    )



    email : EmailStr
    password : str = Field(..., min_length = 8 , max_length = 128)


class CBTStaffAuthResponse(BaseModel):
    model_config = ConfigDict(
        frozen = True
    )

    actor_id : UUID
    membership_id : UUID | None = None

    tenant_id : UUID

    role : Literal[
        "admin",
        "teacher"
    ]

    email : EmailStr
    first_name : str | None = None
    last_name : str | None = None




