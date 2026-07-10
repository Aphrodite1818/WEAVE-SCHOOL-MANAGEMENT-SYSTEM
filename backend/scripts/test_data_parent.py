"""
Fills parents_import_template.xlsx with 1000 rows of fake data.
Requires: pip install openpyxl faker
"""

from pathlib import Path
from openpyxl import load_workbook
from faker import Faker

FILE_PATH = Path(r"C:\Users\taiwo\Downloads\parents_import_template.xlsx")
ROW_COUNT = 50
BASE_EMAIL_USER = "dfragraid"
BASE_EMAIL_DOMAIN = "gmail.com"

HEADERS = [
    "email",
    "first_name",
    "last_name",
    "phone_number",
    "occupation",
    "address",
    "emergency_phone",
]

fake = Faker()


def random_phone() -> str:
    return f"+1{fake.msisdn()[-10:]}"


def build_row(index: int) -> list:
    email = f"{BASE_EMAIL_USER}+parent{index}@{BASE_EMAIL_DOMAIN}"
    return [
        email,
        fake.first_name(),
        fake.last_name(),
        random_phone(),
        fake.job(),
        fake.address().replace("\n", ", "),
        random_phone(),
    ]


def main() -> None:
    wb = load_workbook(FILE_PATH)
    sheet = wb.active

    existing_headers = [cell.value for cell in sheet[1]]
    if existing_headers[: len(HEADERS)] != HEADERS:
        for col_index, header in enumerate(HEADERS, start=1):
            sheet.cell(row=1, column=col_index, value=header)

    for row_offset in range(ROW_COUNT):
        row_number = row_offset + 2
        row_data = build_row(row_offset + 1)
        for col_index, value in enumerate(row_data, start=1):
            sheet.cell(row=row_number, column=col_index, value=value)

    wb.save(FILE_PATH)
    print(f"Wrote {ROW_COUNT} rows to {FILE_PATH}")


if __name__ == "__main__":
    main()