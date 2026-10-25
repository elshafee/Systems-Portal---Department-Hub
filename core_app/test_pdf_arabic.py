from services.pdf_converter import convert_docx_to_pdf
from services.word_editor import replace_placeholders
import os

# Build a test document with Arabic text
input_path = "template_essic.docx"
test_docx = "test_arabic.docx"
test_pdf = "test_arabic.pdf"

replace_placeholders(input_path, test_docx, {
    "{{CODE_NUMBER}}": "0001 ESSIC 07-2026",
    "{{SEND_TO}}": "السيد رئيس الجامعة",
    "{{SUBJECT}}": "طلب اعتماد",
    "{{STACK_HOLDER}}": "الأستاذ الدكتور / محمد كمال عبدالسلام – الموقر",
    "{{POSITION}}": "رئيس مجلس أمناء مركز إيسك",
    "{{BODY_TEXT}}": "نتقدم لسيادتكم بخالص التحية والتقدير",
    "{{SENDER}}": "م/ احمد الشافعى",
})

ok = convert_docx_to_pdf(test_docx, test_pdf)
print(f"Success: {ok}, Size: {os.path.getsize(test_pdf) if ok else 0} bytes")

# Clean up docx but keep PDF for inspection
if os.path.exists(test_docx):
    os.remove(test_docx)
if os.path.exists(test_pdf):
    os.remove(test_pdf)
