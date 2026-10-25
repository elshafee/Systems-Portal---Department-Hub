from docx import Document
from docx.oxml.ns import qn

doc = Document("template_essic.docx")

for p in doc.paragraphs:
    print(f"[{p.text}]")
    if "ﺗﺤﯿﺔ طيبة وﺑﻌﺪ،" in p.text or "ﯿﺒﺔ ط" in p.text or "تحية طيبة" in p.text:
        print("Found greeting, fixing it...")
        # Clear runs and insert fresh Arabic text
        p.text = "تحية طيبة وبعد،"
        
        # Apply standard formatting
        if p.runs:
            run = p.runs[0]
            run.font.name = 'Arial Unicode MS'
            # Force RTL
            rPr = run._element.get_or_add_rPr()
            rFonts = rPr.get_or_add_rFonts()
            rFonts.set(qn('w:cs'), 'Arial Unicode MS')

    # Fix any SENDER issues
    if "SENDER" in p.text:
        print("Found SENDER, fixing it...")
        p.text = "{{SENDER}}"
        if p.runs:
            run = p.runs[0]
            run.font.name = 'Arial Unicode MS'
            run.font.bold = True
            run.font.size = 19 * 12700  # Pt(19) but in docx it's not needed directly if we import Pt

doc.save("template_essic.docx")
print("Template fixed.")
