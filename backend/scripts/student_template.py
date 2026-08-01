"""
Generate 1000 mock student records for the students_import_template.xlsx file.

Columns produced (in order):
    first_name, last_name, date_of_birth, gender, class_name, class_arm,
    state_of_origin, parent_email_1, parent_relationship_1,
    parent_email_2, parent_relationship_2

parent_email_1/2 and parent_relationship_1/2 are left blank as requested.

Usage:
    python generate_students.py [output_path]

If no output_path is given, the file is written to:
    students_import_template_filled.xlsx
"""

import os
import random
import sys
from datetime import date

from faker import Faker
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font

# ---------------------------------------------------------------------------
# CONFIG - change this to write to a different file/location.
# You can use a plain path, e.g.:
#   OUTPUT_PATH = r"C:\Users\taiwo\Downloads\students_import_template (1).xlsx"
# A command-line argument (see bottom of file) will override this if given.
# ---------------------------------------------------------------------------
OUTPUT_PATH = r"C:\Users\taiwo\Downloads\students_import_template (1).xlsx"
NUM_STUDENTS = 1000

fake = Faker()
Faker.seed()  # remove/seed with an int for reproducible output
random.seed()

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

# (class_name, [arms], approximate age range for that class)
CLASS_DEFINITIONS = [
    ("JSS1", ["A", "B"], (10, 11)),
    ("JSS2", ["A", "B"], (11, 12)),
    ("JSS3", ["A", "B"], (12, 13)),
    ("SS1", ["ART", "COMMERCIAL", "SCIENCE"], (14, 15)),
    ("SS2", ["ART", "COMMERCIAL", "SCIENCE"], (15, 16)),
    ("SS3", ["ART", "COMMERCIAL", "SCIENCE"], (16, 17)),
]

# Expand into a flat list of (class_name, class_arm, min_age, max_age)
CLASS_ARM_CHOICES = [
    (class_name, arm, age_range[0], age_range[1])
    for class_name, arms, age_range in CLASS_DEFINITIONS
    for arm in arms
]

NIGERIAN_STATES = [
    "Abia",
    "Adamawa",
    "Akwa Ibom",
    "Anambra",
    "Bauchi",
    "Bayelsa",
    "Benue",
    "Borno",
    "Cross River",
    "Delta",
    "Ebonyi",
    "Edo",
    "Ekiti",
    "Enugu",
    "Gombe",
    "Imo",
    "Jigawa",
    "Kaduna",
    "Kano",
    "Katsina",
    "Kebbi",
    "Kogi",
    "Kwara",
    "Lagos",
    "Nasarawa",
    "Niger",
    "Ogun",
    "Ondo",
    "Osun",
    "Oyo",
    "Plateau",
    "Rivers",
    "Sokoto",
    "Taraba",
    "Yobe",
    "Zamfara",
    "Federal Capital Territory",
]

GENDERS = ["Male", "Female"]

HEADERS = [
    "first_name",
    "last_name",
    "date_of_birth",
    "gender",
    "class_name",
    "class_arm",
    "state_of_origin",
    "parent_email_1",
    "parent_relationship_1",
    "parent_email_2",
    "parent_relationship_2",
]


def random_dob(min_age: int, max_age: int) -> date:
    """Return a random date of birth for a student roughly min_age-max_age years old today."""
    today = date.today()
    start = today.replace(year=today.year - max_age - 1)
    end = today.replace(year=today.year - min_age)
    return fake.date_between(start_date=start, end_date=end)


def generate_student():
    gender = random.choice(GENDERS)
    first_name = fake.first_name_male() if gender == "Male" else fake.first_name_female()
    last_name = fake.last_name()
    class_name, class_arm, min_age, max_age = random.choice(CLASS_ARM_CHOICES)
    dob = random_dob(min_age, max_age)
    state_of_origin = random.choice(NIGERIAN_STATES)

    return [
        first_name,
        last_name,
        dob.strftime("%Y-%m-%d"),
        gender,
        class_name,
        class_arm,
        state_of_origin,
        "",  # parent_email_1
        "",  # parent_relationship_1
        "",  # parent_email_2
        "",  # parent_relationship_2
    ]


def main():
    output_path = sys.argv[1] if len(sys.argv) > 1 else OUTPUT_PATH
    num_students = NUM_STUDENTS

    if os.path.exists(output_path):
        # Existing template found: open it and append below whatever is
        # already there (keeps its existing header/formatting untouched).
        wb = load_workbook(output_path)
        ws = wb.active
        start_row = ws.max_row + 1
        if ws.max_row == 1 and all(c.value is None for c in ws[1]):
            # Sheet is completely empty - write the header first.
            ws.append(HEADERS)
            for cell in ws[1]:
                cell.font = Font(name="Arial", bold=True)
            start_row = 2
    else:
        # No existing file: create a brand new workbook with headers.
        wb = Workbook()
        ws = wb.active
        ws.title = "Students"
        ws.append(HEADERS)
        for cell in ws[1]:
            cell.font = Font(name="Arial", bold=True)
        start_row = 2

        widths = [14, 14, 14, 10, 12, 12, 20, 22, 20, 22, 20]
        for i, width in enumerate(widths, start=1):
            ws.column_dimensions[chr(64 + i)].width = width

    body_font = Font(name="Arial")
    for _ in range(num_students):
        ws.append(generate_student())

    for row in ws.iter_rows(min_row=start_row, max_row=ws.max_row):
        for cell in row:
            cell.font = body_font

    wb.save(output_path)
    print(f"Wrote {num_students} student records to {output_path}")


if __name__ == "__main__":
    main()
