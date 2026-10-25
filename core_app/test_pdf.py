from services.pdf_converter import convert_docx_to_pdf
import os

docx = "template_essic.docx"
pdf  = "test_output.pdf"

if os.path.exists(pdf):
    os.remove(pdf)

ok = convert_docx_to_pdf(docx, pdf)
print(f"Success: {ok}")
print(f"PDF exists: {os.path.exists(pdf)}")
if os.path.exists(pdf):
    print(f"PDF size: {os.path.getsize(pdf)} bytes")
    os.remove(pdf)
