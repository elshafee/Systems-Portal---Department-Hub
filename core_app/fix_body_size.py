from docx import Document
from docx.shared import Pt
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

doc = Document("template_essic.docx")

for p in doc.paragraphs:
    if "{{BODY_TEXT}}" in p.text:
        for run in p.runs:
            run.font.size = Pt(16)
            rPr = run._element.get_or_add_rPr()
            half_pts = str(int(16 * 2))  # 32
            sz = rPr.find(qn('w:sz'))
            szCs = rPr.find(qn('w:szCs'))
            if sz is None:
                sz = OxmlElement('w:sz'); rPr.append(sz)
            sz.set(qn('w:val'), half_pts)
            if szCs is None:
                szCs = OxmlElement('w:szCs'); rPr.append(szCs)
            szCs.set(qn('w:val'), half_pts)
        print("Updated BODY_TEXT to 16pt")

doc.save("template_essic.docx")
print("Saved.")
