from docx import Document
doc = Document("template_essic.docx")
for p in doc.paragraphs[-4:]:
    print(f"[{p.text}]")
    for r in p.runs:
        print(f"  Run: {r.text}, bold: {r.font.bold}, size: {r.font.size.pt if r.font.size else None}")
