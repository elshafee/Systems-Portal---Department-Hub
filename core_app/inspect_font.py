from docx import Document
doc = Document("template_essic.docx")
for p in doc.paragraphs:
    if "{{BODY_TEXT}}" in p.text:
        print("Found BODY_TEXT")
        for r in p.runs:
            print(f"Run text: {r.text}, size: {r.font.size.pt if r.font.size else 'None'}")
