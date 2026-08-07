"""
Generate mock student records for the students_import_template.xlsx file.

Columns produced (in order):
    first_name, last_name, date_of_birth, gender, class_name, class_arm,
    state_of_origin, parent_email_1, parent_relationship_1,
    parent_email_2, parent_relationship_2

parent_email_1 and parent_email_2 are auto-generated using the Gmail "+alias"
trick off a single generic inbox (dfragraid@gmail.com), e.g.:
    dfragraid+1@gmail.com, dfragraid+2@gmail.com, dfragraid+3@gmail.com, ...
Each parent slot (email_1 and email_2, for every row) gets its own unique,
sequentially-incrementing alias number.

parent_relationship_1/2 are randomly picked from a small set of common
relationships (Father/Mother/Guardian).

Usage:
    python generate_students.py [output_path] [num_students]

If no output_path is given, the file is written to:
    students_import_template_filled.xlsx

If no num_students is given, defaults to NUM_STUDENTS below.
"""

import os
import random
import sys
from datetime import date

from faker import Faker
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

# ---------------------------------------------------------------------------
# CONFIG - change this to write to a different file/location.
# You can use a plain path, e.g.:
#   OUTPUT_PATH = r"C:\Users\taiwo\Downloads\students_import_template (1).xlsx"
# Command-line arguments (see bottom of file) will override these if given.
# ---------------------------------------------------------------------------
OUTPUT_PATH = r"C:\Users\taiwo\Downloads\students_import_template.xlsx"
NUM_STUDENTS = 30

# Generic parent inbox used for the "+alias" trick.
PARENT_EMAIL_LOCAL = "dfragraid"
PARENT_EMAIL_DOMAIN = "gmail.com"

fake = Faker()
Faker.seed()  # remove/seed with an int for reproducible output
random.seed()

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

# (class_name, [arms], approximate age range for that class)
# class_name matches the exact naming used in the school's class list
# (e.g. "SS1ART", "SS2COMMERCIAL", "SS3SCIENCE" - no space before the arm).
CLASS_DEFINITIONS = [
    ("JSS1", ["A", "B", "C"], (10, 11)),
    ("JSS2", ["A", "B", "C"], (11, 12)),
    ("JSS3", ["A", "B", "C"], (12, 13)),
    ("SS1ART", ["A", "B", "C"], (14, 15)),
    ("SS1COMMERCIAL", ["A", "B", "C"], (14, 15)),
    ("SS1SCIENCE", ["A", "B", "C"], (14, 15)),
    ("SS2ART", ["A", "B", "C"], (15, 16)),
    ("SS2COMMERCIAL", ["A", "B", "C"], (15, 16)),
    ("SS2SCIENCE", ["A", "B", "C"], (15, 16)),
    ("SS3ART", ["A", "B", "C"], (16, 17)),
    ("SS3COMMERCIAL", ["A", "B", "C"], (16, 17)),
    ("SS3SCIENCE", ["A", "B", "C"], (16, 17)),
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

PARENT_RELATIONSHIPS = ["Father", "Mother", "Guardian"]

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


def next_parent_email(counter: int) -> str:
    """Return the next aliased parent email, e.g. dfragraid+7@gmail.com."""
    return f"{PARENT_EMAIL_LOCAL}+{counter}@{PARENT_EMAIL_DOMAIN}"


def generate_student(email_counter):
    """
    email_counter: a mutable single-item list used as a shared counter so
    every parent_email_1/parent_email_2 across all rows gets its own unique,
    sequential alias number (e.g. +1, +2, +3, ...).
    """
    gender = random.choice(GENDERS)
    first_name = fake.first_name_male() if gender == "Male" else fake.first_name_female()
    last_name = fake.last_name()
    class_name, class_arm, min_age, max_age = random.choice(CLASS_ARM_CHOICES)
    dob = random_dob(min_age, max_age)
    state_of_origin = random.choice(NIGERIAN_STATES)

    parent_email_1 = next_parent_email(email_counter[0])
    email_counter[0] += 1
    parent_relationship_1 = random.choice(PARENT_RELATIONSHIPS)

    parent_email_2 = next_parent_email(email_counter[0])
    email_counter[0] += 1
    # Second relationship should differ from the first where sensible.
    remaining = [
        r for r in PARENT_RELATIONSHIPS if r != parent_relationship_1
    ] or PARENT_RELATIONSHIPS
    parent_relationship_2 = random.choice(remaining)

    return [
        first_name,
        last_name,
        dob.strftime("%Y-%m-%d"),
        gender,
        class_name,
        class_arm,
        state_of_origin,
        parent_email_1,
        parent_relationship_1,
        parent_email_2,
        parent_relationship_2,
    ]


def main():
    output_path = sys.argv[1] if len(sys.argv) > 1 else OUTPUT_PATH
    num_students = int(sys.argv[2]) if len(sys.argv) > 2 else NUM_STUDENTS

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

        widths = [14, 14, 14, 10, 16, 12, 20, 26, 20, 26, 20]
        for i, width in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(i)].width = width

    body_font = Font(name="Arial")

    # Shared counter (list so it mutates across calls) so every parent email
    # across the whole run gets a unique +N alias, continuing on from any
    # rows already present in the file if you re-run this against the same
    # output file.
    email_counter = [1]

    for _ in range(num_students):
        ws.append(generate_student(email_counter))

    for row in ws.iter_rows(min_row=start_row, max_row=ws.max_row):
        for cell in row:
            cell.font = body_font

    wb.save(output_path)
    print(f"Wrote {num_students} student records to {output_path}")
    print(f"Parent email aliases used: +1 through +{email_counter[0] - 1}")


if __name__ == "__main__":
    main()
