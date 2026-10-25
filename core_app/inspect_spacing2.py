from docx import Document
doc = Document("template_essic.docx")
for i, p in enumerate(doc.paragraphs):
    text = p.text[:50].strip() if p.text.strip() else 'EMPTY'
    print(f"P{i} [{text}]")
