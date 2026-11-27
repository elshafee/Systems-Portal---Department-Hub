import os, sys, subprocess, fitz
from PIL import Image

sys.path.insert(0, 'core_app')
from services.word_editor import replace_placeholders
from docx import Document
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

body_sample = """مقترح مجالات التعاون المشترك بين كلية الهندسة - جامعة حورس ومعهد تكنولوجيا المعلومات (ITI) فرع دمياط
نحن في كلية الهندسة بجامعة حورس نتطلع إلى قطاع خدمة المجتمع وتنمية البيئة باعتباره حلقة الوصل بين الإمكانات العلمية للكلية واحتياجات المجتمع وسوق العمل.
ونتطلع إلى أن يتجاور تعاوننا إطار الدورات التدريبية التقليدية ليشمل التأهيل المهني والابتكار والتحول الرقمي للمؤسسات الصناعية والخدمية، مع إتاحة الفرصة لطلابنا وخريجينا للمشاركة في حل تحديات واقعية.
ونأمل أن نتوج من اجتماعنا اليوم بثلاث مبادرات محددة قابلة للتنفيذ خلال الأشهر الثلاثة المقبلة، يتولى تنفيذها فريق عمل مشترك من الجانبين، مع أهداف واضحة ومؤشرات قياس النتائج.
رؤية مقترحة من منظور وكيل لكلية لشؤون خدمة المجتمع وتنمية البيئة / العام الجامعي 2027/2026
أولاً: الرؤية الإستراتيجية للتعاون
تم توقيع بروتوكول تعاون بين كلية الهندسة بجامعة حورس ومعهد ITI دمياط بتاريخ 19 أبريل 2026، بحضور عميد الكلية الأستاذ الدكتور حاتم خاطر والدكتورة إيمان رسلان مدير فرع المعهد. وقد شمل الإعلان التدريب في الذكاء الاصطناعي والأمن السيبراني والحوسبة السحابية والبرامج المهنية.
تفعيل البروتوكول القائم وتوسيعه من التدريب إلى المشروعات المشتركة، وليس مجرد اجتماع لبحث توقيع بروتوكول جديد.
الأهداف الرئيسية"""

replacements = {
    '{{CODE_NUMBER}}': 'No. 12 ENG.CSED 27-11-2026',
    '{{SEND_TO}}': 'مكتب نائب رئيس الجامعة لشؤون التعليم والطلاب',
    '{{SUBJECT}}': 'طلب توفير مقر مناسب وتجهيزات لمركز الخدمات الإلكترونية والإبداع العلمي',
    '{{STACK_HOLDER}}': 'الأستاذ الدكتور / محمد ضبعون',
    '{{POSITION}}': 'نائب رئيس الجامعة لشؤون التعليم والطلاب',
    '{{BODY_TEXT}}': body_sample,
    '{{SENDER}}': '',
    '{{SENDER_TOP}}': 'مدير مركز الخدمات الإلكترونية والإبداع العلمي',
}

for sp_before in [500, 650, 800]:
    out_docx = f'scratch/test_sp_{sp_before}.docx'
    out_pdf = f'scratch/test_sp_{sp_before}.pdf'
    
    replace_placeholders('core_app/template_vice_dean.docx', out_docx, replacements, remove_header_table=False, table_values_align='right')
    
    # Adjust spacing in generated docx for testing
    doc = Document(out_docx)
    # 1. Salutation
    for p in doc.paragraphs:
        if 'وتفضلوا بقبول' in p.text:
            pPr = p._p.get_or_add_pPr()
            for old in list(pPr):
                if old.tag.endswith('spacing'):
                    pPr.remove(old)
            pPr.append(parse_xml(f'<w:spacing {nsdecls("w")} w:before="60" w:after="120" w:line="240" w:lineRule="auto"/>'))
    
    # 2. Signature table
    t2 = doc.tables[2]
    sig_cell = t2.rows[0].cells[1]
    p_top = sig_cell.paragraphs[0]
    pPr_top = p_top._p.get_or_add_pPr()
    for old in list(pPr_top):
        if old.tag.endswith('spacing'):
            pPr_top.remove(old)
    pPr_top.append(parse_xml(f'<w:spacing {nsdecls("w")} w:before="{sp_before}" w:after="20" w:line="240" w:lineRule="auto"/>'))
    
    doc.save(out_docx)
    
    subprocess.run(['/Applications/LibreOffice.app/Contents/MacOS/soffice', '--headless', '--convert-to', 'pdf', out_docx, '--outdir', 'scratch'], check=True)
    
    doc_pdf = fitz.open(out_pdf)
    page_count = len(doc_pdf)
    page = doc_pdf[0]
    
    txt_coords = {}
    for b in page.get_text('blocks'):
        txt = b[4].strip().replace('\n', ' ')
        if 'وتفضلوا' in txt:
            txt_coords['thanks'] = (b[1], b[3])
        elif 'وكيل كلية' in txt:
            txt_coords['title'] = (b[1], b[3])
        elif 'محمد كمال' in txt:
            txt_coords['name'] = (b[1], b[3])
            
    gap = txt_coords['title'][0] - txt_coords['thanks'][1] if 'title' in txt_coords and 'thanks' in txt_coords else 0
    name_bottom = txt_coords['name'][1] if 'name' in txt_coords else 0
    print(f'sp_before={sp_before}: pages={page_count}, thanks_y1={txt_coords.get("thanks", (0,0))[1]:.1f}, title_y0={txt_coords.get("title", (0,0))[0]:.1f}, GAP={gap:.1f}pt (~{gap*0.03528:.2f}cm), name_bottom={name_bottom:.1f}pt')

    # Save render
    pix = page.get_pixmap(dpi=150)
    pix.save(f'scratch/render_sp_{sp_before}.png')
