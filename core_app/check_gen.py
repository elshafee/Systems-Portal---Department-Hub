from docx import Document
doc = Document("generated/Direct_202607d_111902_0007_ESSIC_07-2026.docx")
for i, p in enumerate(doc.paragraphs):
    print(f"P{i}: [{p.text[:100] if p.text.strip() else 'EMPTY'}]")
