from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_LINE_SPACING

doc = Document("template_essic.docx")

for p in doc.paragraphs:
    if "{{BODY_TEXT}}" in p.text:
        pf = p.paragraph_format
        # The font size is 19pt. 
        # A normal line spacing would be ~1.2 * 19 = 22.8pt
        # To make it compact, let's force it to 22pt or 20pt Exactly
        pf.line_spacing_rule = WD_LINE_SPACING.EXACTLY
        pf.line_spacing = Pt(22)
        pf.space_before = Pt(0)
        pf.space_after = Pt(0)
        print("Fixed BODY_TEXT spacing")

doc.save("template_essic.docx")
print("Saved")
