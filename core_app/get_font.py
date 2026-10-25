from docx import Document
doc = Document("template_essic.docx")
for p in doc.paragraphs:
    if "{{BODY_TEXT}}" in p.text:
        print("Paragraph:", p.text)
        for r in p.runs:
            print("Run text:", r.text)
            print("Font name:", r.font.name)
            if r._element.rPr is not None:
                fonts = r._element.rPr.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rFonts")
                if fonts is not None:
                    print("XML rFonts attributes:", fonts.attrib)
