from docx import Document
doc = Document("template_essic.docx")
for i, p in enumerate(doc.paragraphs):
    print(f"P{i}: [{p.text[:80] if p.text.strip() else 'EMPTY'}]")
