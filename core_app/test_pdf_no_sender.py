from services.pdf_converter import convert_docx_to_pdf
from services.word_editor import replace_placeholders
import os

input_path = "template_essic.docx"
test_docx = "test_no_sender.docx"
test_pdf = "test_no_sender.pdf"

replace_placeholders(input_path, test_docx, {
    "{{CODE_NUMBER}}": "0001 ESSIC 07-2026",
    "{{SEND_TO}}": "السيد رئيس الجامعة",
    "{{SUBJECT}}": "طلب اعتماد",
    "{{STACK_HOLDER}}": "الأستاذ الدكتور / محمد كمال عبدالسلام – الموقر",
    "{{POSITION}}": "رئيس مجلس أمناء مركز إيسك",
    "{{BODY_TEXT}}": "نتقدم لسيادتكم بخالص التحية والتقدير",
    "{{SENDER}}": "",
}, remove_manager_sig=False)

ok = convert_docx_to_pdf(test_docx, test_pdf)
print(f"Success without sender: {ok}")

replace_placeholders(input_path, "test_with_sender.docx", {
    "{{CODE_NUMBER}}": "0002 ESSIC 07-2026",
    "{{SEND_TO}}": "السيد رئيس الجامعة",
    "{{SUBJECT}}": "طلب اعتماد داخلي",
    "{{STACK_HOLDER}}": "الأستاذ الدكتور / محمد كمال عبدالسلام – الموقر",
    "{{POSITION}}": "رئيس مجلس أمناء مركز إيسك",
    "{{BODY_TEXT}}": "نتقدم لسيادتكم بخالص التحية والتقدير",
    "{{SENDER}}": "م/ احمد الشافعى",
}, remove_manager_sig=True)

ok2 = convert_docx_to_pdf("test_with_sender.docx", "test_with_sender.pdf")
print(f"Success with sender: {ok2}")
