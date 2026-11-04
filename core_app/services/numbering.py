"""
services/numbering.py

Handles auto-incrementing document number generation.
Numbers reset every month/year combination.

Format ESSIC: 0031 ESSIC 05-2026
Format Vice Dean (CSED): 8 ENG.CSED 31-10-2026
"""

import re
import os
from datetime import datetime
from models import db, Document

DEFAULT_OFFICE_CODE = os.environ.get("SYSTEM_OFFICE_CODE", "ESSIC")

def get_next_serial(month: int, year: int, office_code: str = None) -> int:
    """
    Returns the next sequential serial number for the given month/year and office_code.
    Queries the database to find the highest number for that period.
    Resets to 1 when a new month or year begins.
    """
    code = office_code or DEFAULT_OFFICE_CODE
    # Treat HUEED and CSED as the same office for serial continuation
    search_codes = ['CSED', 'HUEED'] if code.upper() in ('CSED', 'HUEED', 'ENG.CSED') else [code]
    query = db.session.query(Document).filter_by(month=month, year=year)
    if hasattr(Document, 'office_code'):
        query = query.filter(Document.office_code.in_(search_codes))
    last = query.order_by(Document.serial_number.desc()).first()
    return (last.serial_number + 1) if last else 1


def build_full_code(serial: int, month: int, year: int, office_code: str = None, day: int = None) -> str:
    """
    Builds the formatted document code string.
    Example ESSIC: 0031 ESSIC 05-2026
    Example CSED / Vice Dean: No. 8 ENG.CSED 31-10-2026
    """
    code = (office_code or DEFAULT_OFFICE_CODE).upper()
    if code in ('CSED', 'HUEED', 'ENG.CSED'):
        d = day if day is not None else datetime.now().day
        return f"No. {serial} ENG.CSED {d:02d}-{month:02d}-{year}"
    return f"{serial:04d} {code} {month:02d}-{year}"

