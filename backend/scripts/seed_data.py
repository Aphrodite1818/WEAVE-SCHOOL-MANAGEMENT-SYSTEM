"""
Generates fake student data as an Excel (.xlsx) file, using the Faker library.

Academic placement is expressed as three independent fields — level, arm,
and (where applicable) department — matching Weave's current student
import contract. Full class display names like "JSS1 A" or "SS1 B" are
NOT written anywhere; the import template expects level/arm/department
as separate columns instead.

Columns:
first_name, last_name, date_of_birth, gender, level, department, arm,
state_of_origin, parent_email_1, parent_relationship_1, parent_email_2,
parent_relationship_2

parent_email_* and parent_relationship_* are left empty on purpose.

Levels/arms/departments below are pulled from the school's actual
snapshot data. Edit ARMS_BY_LEVEL / DEPARTMENTS_BY_LEVEL if your
level or arm list changes.

This script only ADDS rows to an already-downloaded Weave import
template — it never builds a workbook from scratch when that template
exists, and it never touches any sheet other than the student data
sheet (so the signed `_import_metadata` sheet and the `Instructions`
sheet are left completely untouched).

Requires: pip install faker openpyxl
"""

import os
import random

from faker import Faker
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font

# Nigerian locale gives more realistic Nigerian first/last names
fake = Faker("en_NG")

# ---- Config ----------------------------------------------------------
NUM_ROWS = 1000  # how many fake students to generate

# IMPORTANT: on Windows, this must be a raw string (the r prefix below)
# or forward slashes. Without it, backslash sequences like \U, \t, \n
# get interpreted as escape codes and can crash the script or silently
# mangle the path.
OUTPUT_FILE = r"c:\Users\taiwo\Downloads\students_import_template (15).xlsx"

# Arms available, grouped by level (from the school snapshot). The import
# template wants level and arm as separate columns — not a combined class
# display name like "JSS1 A".
ARMS_BY_LEVEL = {
    "JSS1": ["A", "B"],
    "JSS2": ["A", "B"],
    "JSS3": ["A", "B"],
    "SS1": ["A", "B"],
    "SS2": ["A", "B"],
    "SS3": ["A", "B"],
}


# Roughly the age (in years) a student in each level would be
AGE_RANGE_BY_LEVEL = {
    "JSS1": (10, 11),
    "JSS2": (11, 12),
    "JSS3": (12, 13),
    "SS1": (13, 14),
    "SS2": (14, 15),
    "SS3": (15, 16),
}

# Nigerian states (Faker has no built-in "state" provider for en_NG)
STATES_OF_ORIGIN = [
    "Lagos",
    "Ogun",
    "Oyo",
    "Kano",
    "Rivers",
    "Enugu",
    "Kaduna",
    "Abia",
    "Delta",
    "Edo",
    "Anambra",
    "Imo",
    "Osun",
    "Ondo",
    "Plateau",
    "Benue",
    "Cross River",
    "Akwa Ibom",
    "Sokoto",
    "Borno",
]

FIELDNAMES = [
    "first_name",
    "last_name",
    "date_of_birth",
    "gender",
    "level",
    "department",
    "arm",
    "state_of_origin",
    "parent_email_1",
    "parent_relationship_1",
    "parent_email_2",
    "parent_relationship_2",
]


def random_dob(level: str) -> str:
    """Return a plausible date of birth (YYYY-MM-DD) for the given level."""
    min_age, max_age = AGE_RANGE_BY_LEVEL[level]
    return fake.date_of_birth(minimum_age=min_age, maximum_age=max_age).isoformat()


def generate_row():
    # Level and arm are chosen independently of each other — arm is not
    # derived from or combined into a class display name anywhere.
    level = random.choice(list(ARMS_BY_LEVEL))
    arm = random.choice(ARMS_BY_LEVEL[level])
    gender = random.choice(["Male", "Female"])
    first_name = fake.first_name_male() if gender == "Male" else fake.first_name_female()

    return {
        "first_name": first_name,
        "last_name": fake.last_name(),
        "date_of_birth": random_dob(level),
        "gender": gender,
        "level": level,
        "arm": arm,
        "state_of_origin": random.choice(STATES_OF_ORIGIN),
        "parent_email_1": "",
        "parent_relationship_1": "",
        "parent_email_2": "",
        "parent_relationship_2": "",
    }


def main():
    if os.path.exists(OUTPUT_FILE):
        # Open the existing template as-is. This preserves its formatting,
        # column order, any other sheets, data validation, etc. We only
        # add new rows underneath whatever is already there.
        wb = load_workbook(OUTPUT_FILE)
        ws = wb.active

        # Map "column name" -> column index by reading the existing header
        # row, so this works regardless of what order the template's
        # columns are actually in.
        header_row = 1
        col_map = {}
        for cell in ws[header_row]:
            if cell.value is not None:
                col_map[str(cell.value).strip().lower()] = cell.column

        missing = [name for name in FIELDNAMES if name.lower() not in col_map]
        if missing:
            raise ValueError(
                f"The downloaded template's header row is missing these "
                f"expected column(s): {missing}. This usually means the "
                f"template predates the level/arm/department import "
                f"contract. Download a fresh template from Weave and rerun "
                f"this script against it — do NOT rename or add columns "
                f"in the existing file to work around this."
            )

        start_row = ws.max_row + 1
        for offset in range(NUM_ROWS):
            row_data = generate_row()
            row_idx = start_row + offset
            for name, value in row_data.items():
                ws.cell(row=row_idx, column=col_map[name.lower()], value=value)

        wb.save(OUTPUT_FILE)
        print(f"Appended {NUM_ROWS} fake student rows to the existing file: {OUTPUT_FILE}")

    else:
        # File doesn't exist yet — create it fresh with a header row.
        wb = Workbook()
        ws = wb.active
        ws.title = "Students"

        ws.append(FIELDNAMES)
        for cell in ws[1]:
            cell.font = Font(bold=True)

        for _ in range(NUM_ROWS):
            ws.append(list(generate_row().values()))

        widths = [14, 14, 14, 10, 8, 12, 10, 16, 22, 20, 22, 20]
        for col_idx, width in enumerate(widths, start=1):
            ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = width

        wb.save(OUTPUT_FILE)
        print(
            f"File didn't exist yet — created it with {NUM_ROWS} fake student rows: {OUTPUT_FILE}"
        )


if __name__ == "__main__":
    main()
