"""
services/numbering.py
Auto-incrementing document number — resets every month/year.
Format: 0031 ESSIC 04-2026
"""

from models import db, Document

OFFICE_CODE = "ESSIC"


def get_next_serial(month: int, year: int) -> int:
    last = (
        db.session.query(Document)
        .filter_by(month=month, year=year)
        .order_by(Document.serial_number.desc())
        .first()
    )
    return (last.serial_number + 1) if last else 1


def build_full_code(serial: int, month: int, year: int) -> str:
    """Returns e.g. '0031 ESSIC 04-2026'"""
    return f"{serial:04d} {OFFICE_CODE} {month:02d}-{year}"
