#==========================#
#  bulk_import schemas .py # 
#==========================#


"""pydantic schemas for tenant bulk import workflows"""


from __future__ import annotations 
import uuid
from datetime import datetime 
from typing import Any 


from pydantic import BaseModel , ConfigDict, Field , field_validator




from app.modules.bulk_imports.models import(
    ImportFileType,
    ImportJobStatus,
    ImportNotificationChannel,
    ImportNotificationStatus,
    ImportResourceType
)



class InputBase(BaseModel):
    """Base schema for import request / input payloads"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        str_to_lower = False ,
        extra = "forbid",
        use_enum_values = True
    )




class OutputBase(BaseModel):
    """Base schema for import output / response payloads"""

    model_config = ConfigDict(
        from_attributes= True ,
        use_enum_values=True,
        populate_by_name=True
    )



def _clean_optional_string(value : str | None) -> str | None:
    if value is None:
        return None
    
    cleaned_value = value.strip()
    return cleaned_value or None





class ImportOptions(InputBase):
    """Optional controls for an import uploads"""

    dry_run : bool = Field(
        default = False,
        description = "Validate the file without creating records"
    )

    notify_on_completion : bool = Field(
        default = True ,
        description = "Create an admin notification after processing"
    )




class ImportJobCreate(InputBase):
    """Internal payload for creating an import job"""

    resource_type : ImportResourceType
    file_type : ImportFileType
    original_filename : str = Field(..., min_length = 1 , max_length = 255)
    stored_filename : str | None = Field(default = None , max_length=255)
    source_file_path : str | None = None
    file_size_bytes : int | None = Field(default = None , ge = 0)
    created_by_admin_id : uuid.UUID | None = None 
    metadata_json : dict[str , Any] | None = None

    @field_validator(
        "original_filename",
        "stored_filename",
        "source_file_path",
        mode= "before"
    )
    @classmethod
    def clean_optional_text(cls , value : str | None) -> None | str:
        """normalize optional text fields"""

        return _clean_optional_string(value)
    




class ImportJobUpdate(InputBase):
    """Internal payload schema for updating an import job"""


    status: ImportJobStatus | None = None
    stored_filename: str | None = Field(default=None, max_length=255)
    source_file_path: str | None = None
    result_file_path: str | None = None
    file_size_bytes: int | None = Field(default=None, ge=0)

    total_rows: int | None = Field(default=None, ge=0)
    processed_rows: int | None = Field(default=None, ge=0)
    successful_rows: int | None = Field(default=None, ge=0)
    failed_rows: int | None = Field(default=None, ge=0)
    skipped_rows: int | None = Field(default=None, ge=0)

    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata_json: dict[str, Any] | None = None

    @field_validator(
        "stored_filename",
        "source_file_path",
        "result_file_path",
        "error_message",
        mode="before",
    )
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        """Normalize optional text fields."""

        return _clean_optional_string(value)
    






class ImportRowErrorCreate(InputBase):
    """Input payload for saving a row-level import error"""

    import_job_id : uuid.UUID
    row_number : int = Field(..., ge = 1)
    field_name : str | None = Field(default = None , max_length = 120)
    error_code : str | None = Field(default = None , max_length = 120)
    error_message : str = Field(..., min_length = 1)
    raw_row : dict[str , Any] | None = None
    normalized_row : dict[str , Any] | None = None



    @field_validator("field_name", "error_code", "error_message", mode="before")
    @classmethod
    def clean_text_fields(cls, value: str | None) -> str | None:
        """Normalize row error text fields."""

        return _clean_optional_string(value)
    



class ImportNotificationCreate(InputBase):
    """Internal payload for creating an import notification"""

    import_job_id : uuid.UUID
    recipient_admin_id : uuid.UUID | None = None
    channel : ImportNotificationChannel = ImportNotificationChannel.IN_APP
    status: ImportNotificationStatus = ImportNotificationStatus.PENDING
    title : str = Field(..., min_length = 1 , max_length = 200)
    message : str = Field(..., min_length = 1)
    failure_reason : str | None = None


    @field_validator("title", "message", "failure_reason", mode="before")
    @classmethod
    def clean_text_fields(cls, value: str | None) -> str | None:
        """Normalize notification text fields."""

        return _clean_optional_string(value)
    



class ImportJobSummaryResponse(OutputBase):
    """Compact import job response for import history lists"""


    id : uuid.UUID
    tenant_id : uuid.UUID
    resource_type : ImportResourceType
    file_type : ImportFileType
    status: ImportJobStatus


    original_filename : str 
    stored_filename : str | None = None

    total_rows : int 
    processed_rows : int 
    successful_rows : int 
    failed_rows : int 
    skipped_rows : int 

    error_message : str | None = None 
    started_at : datetime | None = None 
    completed_at : datetime | None = None 
    created_at : datetime
    updated_at : datetime 



class ImportRowErrorResponse(OutputBase):
    """Response schema for a failed import row """


    id : uuid.UUID
    tenant_id : uuid.UUID
    import_job_id : uuid.UUID

    row_number : int 
    field_name : str | None = None 
    error_code : str | None = None 
    error_message : str 


    raw_row : dict[str , Any] | None = None
    normalized_row : dict[str , Any] | None = None

    created_at : datetime
    updated_at: datetime 



class ImportNotificationResponse(OutputBase):
    """Response schema for import notifications"""

    id : uuid.UUID
    tenant_id : uuid.UUID
    import_job_id : uuid.UUID
    recipient_admin_id : uuid.UUID | None = None


    channel : ImportNotificationChannel
    status : ImportNotificationStatus
    title : str 
    message : str 
    is_read : bool


    sent_at : datetime | None = None
    read_at : datetime | None = None
    failure_reason : str | None = None

    created_at : datetime
    updated_at : datetime 






class ImportJobDetailResponse(ImportJobSummaryResponse):
    """Detailed import job response"""


    created_by_admin_id : uuid.UUID | None = None 


    source_file_path : str | None = None
    result_file_path : str | None = None
    file_size_bytes : int | None = None
    metadata_json : dict[str , Any] | None = None

    row_errors : list[ImportRowErrorResponse] = Field(default_factory = list)
    notifications : list[ImportNotificationResponse] = Field(default_factory = list)


class ImportJobListResponse(OutputBase):
    """Paginated - style response for import jobs"""

    items : list[ImportJobSummaryResponse]
    total : int 



class ImportRowErrorListResponse(OutputBase):
    """Paginated style response for import row errors"""

    items : list[ImportRowErrorResponse]
    total : int



class ImportUploadResponse(OutputBase):
    """Response returned after an import file is accepted"""

    job : ImportJobSummaryResponse
    message : str = "Import job created successfully"


class ImportStatusResponse(OutputBase):
    """Compact import procesing status response"""
    id : uuid.UUID
    resource_type : ImportResourceType
    status : ImportJobStatus

    total_rows : int 
    processed_rows : int 
    successful_rows : int 
    failed_rows : int 
    skipped_rows : int 


    error_message : str | None = None 
    started_at : datetime | None = None 
    completed_at : datetime | None = None 




class ImportTemplateColumnResponse(OutputBase):
    """Describes one column in a bulk import template"""

    name : str
    label : str 
    required : bool = False
    example : str | None = None 
    description : str | None = None
    accepted_values : list[str] = Field(default_factory = list )



class ImportTemplateResponse(OutputBase):
    """Response schema for a generated import template"""

    resource_type : ImportResourceType
    file_type : ImportFileType = ImportFileType.CSV
    filename : str 
    columns : list[ImportTemplateColumnResponse]
    notes : list[str] = Field(default_factory=list)



    
