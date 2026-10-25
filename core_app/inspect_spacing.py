from docx import Document
from docx.shared import Pt
doc = Document("template_essic.docx")
for i, p in enumerate(doc.paragraphs):
    pf = p.paragraph_format
    text = p.text[:30].strip() if p.text.strip() else 'EMPTY'
    print(f"P{i} [{text}]: space_before={pf.space_before}, space_after={pf.space_after}, line_spacing={pf.line_spacing}, line_spacing_rule={pf.line_spacing_rule}")
