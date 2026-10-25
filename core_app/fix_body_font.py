from docx import Document
from docx.shared import Pt, RGBColor
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

doc = Document("template_essic.docx")

def set_run_font(run, font_name, size_pt, bold):
    run.font.name = font_name
    run.font.size = Pt(size_pt)
    run.font.bold = bold
    # Set complex script font (used for Arabic rendering)
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = OxmlElement('w:rFonts')
        rPr.insert(0, rFonts)
    rFonts.set(qn('w:cs'), font_name)
    rFonts.set(qn('w:ascii'), font_name)
    rFonts.set(qn('w:hAnsi'), font_name)
    # Also set complex script size
    sz = rPr.find(qn('w:sz'))
    szCs = rPr.find(qn('w:szCs'))
    half_pts = str(int(size_pt * 2))
    if sz is None:
        sz = OxmlElement('w:sz')
        rPr.append(sz)
    sz.set(qn('w:val'), half_pts)
    if szCs is None:
        szCs = OxmlElement('w:szCs')
        rPr.append(szCs)
    szCs.set(qn('w:val'), half_pts)

for p in doc.paragraphs:
    if "{{BODY_TEXT}}" in p.text:
        for run in p.runs:
            set_run_font(run, "Times New Roman", 14, True)
            # keep existing color (red)
        print(f"Updated BODY_TEXT: {[r.text for r in p.runs]}")

doc.save("template_essic.docx")
print("Saved.")
