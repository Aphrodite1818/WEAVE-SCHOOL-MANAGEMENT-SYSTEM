#=============================#
# bulk_imports_normalizers.py #
#============================#


"""Row normalization helpers for tenant bulk imports"""

from __future__ import annotations

import re
from typing import Any

from app.modules.bulk_imports.models import ImportResourceType


class BulkImportNormalizers:
    """Normalize parsed import rows into canonical field names and values"""


    STUDENT_FIELD_ALIASES = {
        "admission_number": "admission_number",
        "admission_no": "admission_number",
        "first_name": "first_name",
        "firstname": "first_name",
        "last_name": "last_name",
        "lastname": "last_name",
        "date_of_birth": "date_of_birth",
        "dob": "date_of_birth",
        "gender": "gender",
        "sex": "gender",
        "state": "state_of_origin",
        "state_of_origin": "state_of_origin",
        "class": "class_name",
        "class_name": "class_name",
        "class_id": "class_id",
        "arm": "arm",
    }




    TEACHER_FIELD_ALIASES = {
        "first_name": "first_name",
        "firstname": "first_name",
        "last_name": "last_name",
        "lastname": "last_name",
        "email": "email",
        "email_address": "email",
        "phone": "phone",
        "phone_number": "phone",
        "gender": "gender",
        "sex": "gender",
        "subject": "subject_name",
        "subject_name": "subject_name",
    }



    PARENT_FIELD_ALIASES = {
        "first_name": "first_name",
        "firstname": "first_name",
        "last_name": "last_name",
        "lastname": "last_name",
        "email": "email",
        "email_address": "email",
        "phone": "phone",
        "phone_number": "phone",
        "student_admission_number": "student_admission_number",
        "admission_number": "student_admission_number",
        "relationship": "relationship_type",
        "relationship_type": "relationship_type",
    }



    CLASS_FIELD_ALIASES = {
        "name": "name",
        "class": "name",
        "class_name": "name",
        "level": "level",
        "arm": "arm",
        "teacher_email": "teacher_email",
    }



    SUBJECT_FIELD_ALIASES = {
        "name": "name",
        "subject": "name",
        "subject_name": "name",
        "code": "code",
        "subject_code": "code",
        "description": "description",
    }




    CLASS_SUBJECT_FIELD_ALIASES = {
        "class": "class_name",
        "class_name": "class_name",
        "arm": "arm",
        "subject": "subject_name",
        "subject_name": "subject_name",
    }





    TEACHER_SUBJECT_FIELD_ALIASES = {
        "teacher_email": "teacher_email",
        "email": "teacher_email",
        "subject": "subject_name",
        "subject_name": "subject_name",
    }





    ASSESSMENT_RECORD_FIELD_ALIASES = {
        "admission_number": "admission_number",
        "student_admission_number": "admission_number",
        "subject": "subject_name",
        "subject_name": "subject_name",
        "score": "score",
        "max_score": "max_score",
        "assessment": "assessment_name",
        "assessment_name": "assessment_name",
        "term": "term_name",
        "term_name": "term_name",
        "session": "session_name",
        "session_name": "session_name",
    }




    FIELD_ALIASES_BY_RESOURCE = {
        ImportResourceType.STUDENTS: STUDENT_FIELD_ALIASES,
        ImportResourceType.TEACHERS: TEACHER_FIELD_ALIASES,
        ImportResourceType.PARENTS: PARENT_FIELD_ALIASES,
        ImportResourceType.CLASSES: CLASS_FIELD_ALIASES,
        ImportResourceType.SUBJECTS: SUBJECT_FIELD_ALIASES,
        ImportResourceType.CLASS_SUBJECTS: CLASS_SUBJECT_FIELD_ALIASES,
        ImportResourceType.TEACHER_SUBJECTS: TEACHER_SUBJECT_FIELD_ALIASES,
        ImportResourceType.ASSESSMENT_RECORDS: ASSESSMENT_RECORD_FIELD_ALIASES,
    }





    @staticmethod
    def normalize_key(key : Any) -> str:
        """Normalize a column name for alias matching"""

        if key is None:
            return ""
        
        normalized_key = str(key).strip().lower()
        normalized_key = re.sub(r"[\s\-]+", "_", normalized_key)
        normalized_key = re.sub(r"[^a-z0-9_]", "", normalized_key)
        return normalized_key
    



    @staticmethod
    def normalize_email(value : Any) -> None | str:
        """Normalize an email value"""

        if value is None:
            return None
        

        email = str(value).strip().lower()
        return email or None
    



    @staticmethod
    def _normalize_phone(value : Any) -> None | str:
        """Normalize a phone value without enforcing country-specific-rules"""

        if value is None:
            return None
        
        phone = str(value).strip()
        phone = re.sub(r"\s+","", phone)
        return phone or None
    



    @staticmethod
    def normalize_gender(value : Any) -> None | str:
        """Normalize common gender inputs"""

        if value is None:
            return None


        gender = str(value).strip().lower()    

        male_values = {"m", "male", "boy"}
        female_values = {"f", "female", "girl"}

        if gender in male_values:
            return "male"
        
        if gender in female_values:
            return "female"
        
        return gender or None
    




    @staticmethod
    def normalize_date_string(value : Any) -> None | str:
        """
        Normalize date like values into strings

        the validator laters confirms whether the date can be parsed
        """


        if value is None:
            return None
        
        value_text = str(value).strip()
        return value_text or None
    




    @staticmethod
    def normalize_title_text(value : Any) -> None | str:
        """Normalize a human-readable text field"""

        if value is None:
            return None
        

        value_text = str(value).strip()
        return " ".join(value_text.split()) or None
    





    @staticmethod
    def normalize_number(value : Any) -> None | int | float | str:
        """Normalize numeric values while preserving invalid values for validation errors"""


        if value is None:
            return None


        if isinstance(value , (int , float)):
            return value
        

        value_text = str(value).strip()

        if not value_text:
            return None
        

        try:
            number_value = float(value_text)

        except ValueError:
            return value_text
        


        if number_value.is_integer():
            return int(number_value)
        
        return number_value







    @staticmethod
    def normalize_value(
        *,
        field_name : str ,
        value : Any
    ):
        """Normalize a field value based on its canonical field name"""


        if value is None:
            return None
        

        if isinstance(value , str):
            value = value.strip()


            if not value:
                return None
            

        if field_name in {"email", "teacher_email"}:
            return BulkImportNormalizers.normalize_email(value)
        

        if field_name in {"phone", "phone_number"}:
            return BulkImportNormalizers._normalize_phone(value)
        

        if field_name == "gender":
            return BulkImportNormalizers.normalize_gender(value)
        
        if field_name in {"date_of_birth", "admissioin_date", "graduation_date"}:
            return BulkImportNormalizers.normalize_date_string(value)
        



        if field_name in {
            "first_name",
            "last_name",
            "state_of_origin",
            "name",
            "level",
            "arm",
            "class_name",
            "subject_name",
            "assessment_name",
            "term_name",
            "session_name",
            "relationship_type",
        }:
            return BulkImportNormalizers.normalize_title_text(value)
        

        if field_name in {
            "admission_number",
            "student_admission_number",
            "class_id",
            "code",
            "subject_code",
        }:
            return BulkImportNormalizers.normalize_number(value)
        
        if isinstance(value , str):
            return value.strip()
        
        return value
    



    @staticmethod
    def normalize_row(
        *,
        resource_type: ImportResourceType,
        raw_row : dict[str,Any]
    ) -> dict[str, Any]:
        """Normalize a parsed row into canonical field names """

        field_aliases = BulkImportNormalizers.FIELD_ALIASES_BY_RESOURCE.get(
            resource_type,
            {}
        )
        normalized_row : dict[str , Any] = {}


        for raw_field_name , raw_value in raw_row.items():
            normalized_field_name = BulkImportNormalizers.normalize_key(raw_field_name)
            canonical_field_name = field_aliases.get(
                normalized_field_name,
                normalized_field_name #defaults to original normalized_field_name if not found in the dictionary
            )

            normalized_row[canonical_field_name] = BulkImportNormalizers.normalize_value(
                field_name = canonical_field_name,
                value = raw_value
            )


        return normalized_row
    



    @staticmethod
    def normalize_rows(
        *,
        resource_type : ImportResourceType,
        raw_rows : list[dict[str , Any]]
    ) -> list[dict[str, Any]]:
        """Normalize multiple parsed rows"""

        return [
            BulkImportNormalizers.normalize_row(
                resource_type = resource_type,
                raw_row= raw_row
            )
            for raw_row in raw_rows
        ]





