from docx import Document
doc = Document("template_essic.docx")
for i, p in enumerate(doc.paragraphs):
    if p.text.strip():
        print(f"P{i}: [{p.text[:80]}]")
    elif "{{" in p.text:
        print(f"P{i}: [{p.text}]")
    else:
        print(f"P{i}: [EMPTY]")
