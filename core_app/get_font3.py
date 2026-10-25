from docx import Document
doc = Document("template_essic.docx")
for p in doc.paragraphs:
    if "عناية" in p.text:
        print("Paragraph:", p.text)
        for r in p.runs:
            print("Run text:", r.text)
            print("Font size:", r.font.size.pt if r.font.size else None)
            print("Bold:", r.font.bold)
