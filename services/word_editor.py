"""
services/word_editor.py

Safe placeholder replacement in Word (.docx) documents.
Replaces {{CODE_NUMBER}} in:
  - paragraphs
  - table cells
  - headers
  - footers

Preserves all formatting, fonts, Arabic text, logos, and layout.
"""

import copy
import os
import re
from docx import Document
from docx.oxml.ns import qn
from docx.shared import Pt
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.oxml import OxmlElement
from docx.text.paragraph import Paragraph

PLACEHOLDER = "{{CODE_NUMBER}}"


def _replace_in_paragraph(paragraph, replacement: str):
    """
    Replace placeholder in a paragraph while preserving run-level formatting.

    Word sometimes splits a placeholder across multiple runs (e.g. {{CODE_ and NUMBER}}).
    We reassemble the full paragraph text, detect the placeholder, then rebuild runs
    carefully to avoid formatting loss.
    """
    full_text = "".join(run.text for run in paragraph.runs)

    if PLACEHOLDER not in full_text:
        return  # nothing to do

    # Replace in the combined text
    new_text = full_text.replace(PLACEHOLDER, replacement)

    # Strategy: put all new text into the FIRST run, clear the rest.
    # This preserves the first run's character formatting for the replaced text.
    if not paragraph.runs:
        return

    paragraph.runs[0].text = new_text
    for run in paragraph.runs[1:]:
        run.text = ""


def _replace_in_table(table, replacement: str):
    """Iterate every cell and every paragraph inside a table."""
    for row in table.rows:
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                _replace_in_paragraph(paragraph, replacement)
            # Tables can be nested
            for nested_table in cell.tables:
                _replace_in_table(nested_table, replacement)


def _replace_in_header_footer(section_part, replacement: str):
    """Replace placeholder inside a header or footer section part."""
    if section_part is None:
        return
    for paragraph in section_part.paragraphs:
        _replace_in_paragraph(paragraph, replacement)
    for table in section_part.tables:
        _replace_in_table(table, replacement)


def replace_placeholder(input_path: str, output_path: str, replacement: str):
    """
    Opens a .docx file, replaces all occurrences of {{CODE_NUMBER}} with
    the provided replacement string, and saves to output_path.

    Args:
        input_path:   Path to the source .docx template.
        output_path:  Path where the modified document will be saved.
        replacement:  The code string to substitute (e.g. '0031 ESSIC 05-2026').
    """
    doc = Document(input_path)

    # 1. Body paragraphs
    for paragraph in doc.paragraphs:
        _replace_in_paragraph(paragraph, replacement)

    # 2. Body tables
    for table in doc.tables:
        _replace_in_table(table, replacement)

    # 3. Headers and footers across all sections
    for section in doc.sections:
        _replace_in_header_footer(section.header, replacement)
        _replace_in_header_footer(section.footer, replacement)
        _replace_in_header_footer(section.even_page_header, replacement)
        _replace_in_header_footer(section.even_page_footer, replacement)
        _replace_in_header_footer(section.first_page_footer, replacement)

    doc.save(output_path)


def process_reserve_document(input_path: str, output_path: str, full_code: str):
    """
    Opens a .docx template when reserving a serial number.
    Replaces {{CODE_NUMBER}} with full_code.
    Replaces {{ESSIC}}, {{HUEED}}, {{AIE}} with empty string.
    Replaces all other placeholders ({{SEND_TO}}, {{SUBJECT}}, {{STACK_HOLDER}},
    {{POSITION}}, {{BODY_TEXT}}, {{SENDER}}, {{SENDER_TOP}}, etc.) with an empty single space " ".
    Preserves all paragraphs and layout intact without deleting empty lines.
    """
    import re
    doc = Document(input_path)

    def _clean_text(text: str):
        if not text:
            return text, False
        modified = False
        if re.search(r'\{\{\s*CODE_NUMBER\s*\}\}', text):
            text = re.sub(r'\{\{\s*CODE_NUMBER\s*\}\}', full_code, text)
            modified = True
        for office_tag in ['ESSIC', 'HUEED', 'AIE']:
            pattern = r'\{\{\s*' + re.escape(office_tag) + r'\s*\}\}'
            if re.search(pattern, text):
                text = re.sub(pattern, '', text)
                modified = True
        if re.search(r'\{\{\s*[A-Za-z0-9_]+\s*\}\}', text):
            text = re.sub(r'\{\{\s*[A-Za-z0-9_]+\s*\}\}', ' ', text)
            modified = True
        return text, modified

    def _process_p(p):
        full_text = "".join(r.text for r in p.runs)
        new_text, modified = _clean_text(full_text)
        if modified:
            if p.runs:
                p.runs[0].text = new_text
                for r in p.runs[1:]:
                    r.text = ""

    for p in doc.paragraphs:
        _process_p(p)

    def _process_t(table):
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    _process_p(p)
                for nested_table in cell.tables:
                    _process_t(nested_table)

    for table in doc.tables:
        _process_t(table)

    for section in doc.sections:
        for part in [section.header, section.footer, section.even_page_header, section.even_page_footer, section.first_page_header, section.first_page_footer]:
            if part is not None:
                for p in part.paragraphs:
                    _process_p(p)
                for t in part.tables:
                    _process_t(t)

    doc.save(output_path)


def update_code_in_docx(file_path: str, old_code: str, new_code: str):
    """
    Replaces old_code with new_code across paragraphs, tables, headers, footers in file_path.
    """
    if not old_code or old_code == new_code or not os.path.exists(file_path):
        return
    doc = Document(file_path)

    def _replace_in_p(p):
        full = "".join(r.text for r in p.runs)
        if old_code in full:
            new_t = full.replace(old_code, new_code)
            if p.runs:
                p.runs[0].text = new_t
                for r in p.runs[1:]:
                    r.text = ""

    def _replace_in_t(table):
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    _replace_in_p(p)
                for nested in cell.tables:
                    _replace_in_t(nested)

    for p in doc.paragraphs:
        _replace_in_p(p)
    for t in doc.tables:
        _replace_in_t(t)
    for sec in doc.sections:
        for part in [sec.header, sec.footer, sec.even_page_header, sec.even_page_footer, sec.first_page_header, sec.first_page_footer]:
            if part is not None:
                for p in part.paragraphs:
                    _replace_in_p(p)
                for t in part.tables:
                    _replace_in_t(t)
    doc.save(file_path)


def replace_placeholders(input_path: str, output_path: str, replacements: dict, remove_manager_sig: bool = False, tables_data: list = None, image_paths: list = None, table_data: list = None, image_sizes: list = None, **kwargs):
    """
    Opens a .docx file, replaces multiple occurrences of keys in `replacements` dict
    with their corresponding values, and saves to output_path.
    If remove_manager_sig is True, it removes the hardcoded manager signature lines.
    """
    if tables_data is None and table_data is not None:
        tables_data = table_data

    doc = Document(input_path)

    def _replace_in_p(paragraph):
        full_text = "".join(run.text for run in paragraph.runs)
        modified = False
        remove_p = False
        modified_body = False

        for k, v in replacements.items():
            if k in full_text:
                if k == "{{BODY_TEXT}}":
                    modified_body = True
                    # Clean up Body Text
                    raw_v = v
                    prefix = ""
                    suffix = ""
                    if raw_v.startswith("\u202B") or raw_v.startswith("\u202A"):
                        prefix = raw_v[0]
                        raw_v = raw_v[1:]
                    if raw_v.endswith("\u202C"):
                        suffix = raw_v[-1]
                        raw_v = raw_v[:-1]
                        
                    # Enforce limits (allow more room if tables or images or rich html are included)
                    import re
                    has_media = bool(re.search(r'\{\{(?:TABLE|IMAGE)_\d+\}\}', raw_v))
                    MAX_WORDS = 800 if has_media else 400
                    MAX_CHARS = 8000 if has_media else 4000
                    raw_v = raw_v.strip()
                    words = raw_v.split()
                    if len(words) > MAX_WORDS:
                        raw_v = " ".join(words[:MAX_WORDS])
                    if len(raw_v) > MAX_CHARS:
                        raw_v = raw_v[:MAX_CHARS].rsplit(" ", 1)[0]
                        
                    # Filter out empty lines
                    lines = [line.strip() for line in raw_v.split("\n") if line.strip()]
                    raw_v = "\n".join(lines)
                    
                    v = prefix + raw_v + suffix

                full_text = full_text.replace(k, v)
                modified = True

        if modified:
            if not full_text.strip():
                paragraph._element.getparent().remove(paragraph._element)
            elif paragraph.runs:
                if modified_body:
                    from html.parser import HTMLParser
                    import re

                    def parse_color_to_rgb(val):
                        if not val:
                            return None
                        val = val.strip().lower()
                        # rgb(...)
                        rgb_match = re.search(r'rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)', val)
                        if rgb_match:
                            try:
                                r = min(255, max(0, int(rgb_match.group(1))))
                                g = min(255, max(0, int(rgb_match.group(2))))
                                b = min(255, max(0, int(rgb_match.group(3))))
                                return (r, g, b)
                            except:
                                pass
                                
                        # hex #RRGGBB or #RGB
                        hex_match = re.search(r'#([0-9a-f]{6}|[0-9a-f]{3})\b', val)
                        if hex_match:
                            h = hex_match.group(1)
                            if len(h) == 3:
                                h = ''.join([c*2 for c in h])
                            r = int(h[0:2], 16)
                            g = int(h[2:4], 16)
                            b = int(h[4:6], 16)
                            return (r, g, b)

                        named_colors = {
                            'black': (0, 0, 0),
                            'white': (255, 255, 255),
                            'red': (220, 38, 38),
                            'blue': (37, 99, 235),
                            'green': (22, 163, 74),
                            'yellow': (234, 179, 8),
                            'orange': (234, 88, 12),
                            'purple': (124, 58, 237),
                            'gray': (107, 114, 128),
                            'grey': (107, 114, 128),
                            'navy': (31, 78, 121),
                            'darkblue': (30, 58, 138),
                            'gold': (217, 119, 6),
                            'maroon': (128, 0, 0),
                            'teal': (13, 148, 136),
                        }
                        for name, rgb in named_colors.items():
                            if f'color:{name}' in val.replace(' ', '') or val == name:
                                return rgb
                                
                        return None

                    def parse_highlight(val):
                        if not val:
                            return None
                        val = val.strip().lower()
                        if 'yellow' in val or '#fef08a' in val or '#ffff00' in val:
                            return 'yellow'
                        if 'green' in val or '#bbf7d0' in val:
                            return 'green'
                        if 'blue' in val or 'cyan' in val or '#bae6fd' in val:
                            return 'cyan'
                        if 'pink' in val or 'magenta' in val or '#fbce8' in val or '#fbcfe8' in val:
                            return 'magenta'
                        if 'orange' in val or '#fed7aa' in val:
                            return 'darkYellow'
                        return None
                    
                    class DocxHTMLParser(HTMLParser):
                        def __init__(self):
                            super().__init__()
                            self.paragraphs = []
                            self.current_runs = []
                            self.current_align = 'right'
                            self.current_dir = 'rtl'
                            self.current_heading = 0
                            self.list_stack = []
                            self.ol_counter_stack = []
                            
                            self.base_format = {'bold': False, 'italic': False, 'underline': False, 'color': None, 'highlight': None}
                            self.format_stack = [self.base_format.copy()]
                            self.tag_stack = []

                        def _flush_paragraph(self):
                            if self.current_runs:
                                self.paragraphs.append({
                                    'runs': self.current_runs,
                                    'alignment': self.current_align,
                                    'direction': self.current_dir,
                                    'heading_level': self.current_heading
                                })
                                self.current_runs = []

                        def handle_starttag(self, tag, attrs):
                            attrs_dict = dict(attrs)
                            style = attrs_dict.get('style', '').lower()
                            align_attr = attrs_dict.get('align', '').lower()
                            dir_attr = attrs_dict.get('dir', '').lower()

                            new_align = None
                            if 'text-align: center' in style or align_attr == 'center':
                                new_align = 'center'
                            elif 'text-align: left' in style or align_attr == 'left':
                                new_align = 'left'
                            elif 'text-align: justify' in style or align_attr == 'justify':
                                new_align = 'justify'
                            elif 'text-align: right' in style or align_attr == 'right':
                                new_align = 'right'

                            new_dir = None
                            if 'direction: ltr' in style or dir_attr == 'ltr':
                                new_dir = 'ltr'
                            elif 'direction: rtl' in style or dir_attr == 'rtl':
                                new_dir = 'rtl'

                            if tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'div']:
                                self._flush_paragraph()
                                if new_dir:
                                    self.current_dir = new_dir
                                else:
                                    self.current_dir = 'rtl'

                                if new_align:
                                    self.current_align = new_align
                                elif not self.list_stack:
                                    self.current_align = 'left' if self.current_dir == 'ltr' else 'right'

                                if tag == 'h1':
                                    self.current_heading = 1
                                elif tag == 'h2':
                                    self.current_heading = 2
                                elif tag in ['h3', 'h4', 'h5', 'h6']:
                                    self.current_heading = 3
                                else:
                                    self.current_heading = 0
                            elif tag == 'ul':
                                self.list_stack.append('ul')
                                self.ol_counter_stack.append(0)
                            elif tag == 'ol':
                                self.list_stack.append('ol')
                                self.ol_counter_stack.append(1)
                            elif tag == 'li':
                                self._flush_paragraph()
                                if new_dir:
                                    self.current_dir = new_dir
                                if new_align:
                                    self.current_align = new_align
                                else:
                                    self.current_align = 'left' if self.current_dir == 'ltr' else 'right'
                                self.current_heading = 0

                                if self.list_stack and self.list_stack[-1] == 'ol':
                                    count = self.ol_counter_stack[-1]
                                    prefix = f'{count}. '
                                    self.ol_counter_stack[-1] += 1
                                else:
                                    prefix = '• '

                                active_fmt = self.format_stack[-1]
                                self.current_runs.append({
                                    'text': prefix,
                                    'bold': True,
                                    'italic': False,
                                    'underline': False,
                                    'color': active_fmt.get('color'),
                                    'highlight': None
                                })

                            overrides = {}
                            if tag in ['strong', 'b'] or 'font-weight: bold' in style or 'font-weight: 700' in style:
                                overrides['bold'] = True
                            if tag in ['em', 'i'] or 'font-style: italic' in style:
                                overrides['italic'] = True
                            if tag in ['u'] or 'text-decoration: underline' in style:
                                overrides['underline'] = True

                            color_val = None
                            if 'color:' in style:
                                m = re.search(r'(?:^|;)\s*color\s*:\s*([^;]+)', style)
                                if m:
                                    color_val = m.group(1).strip()
                            elif tag == 'font' and 'color' in attrs_dict:
                                color_val = attrs_dict['color'].strip()

                            if color_val:
                                rgb = parse_color_to_rgb(color_val)
                                if rgb:
                                    overrides['color'] = rgb

                            bg_val = None
                            if 'background-color:' in style:
                                m = re.search(r'(?:^|;)\s*background-color\s*:\s*([^;]+)', style)
                                if m:
                                    bg_val = m.group(1).strip()
                            elif tag == 'mark':
                                bg_val = 'yellow'

                            if bg_val:
                                hl = parse_highlight(bg_val)
                                if hl:
                                    overrides['highlight'] = hl

                            new_fmt = self.format_stack[-1].copy()
                            new_fmt.update(overrides)
                            self.format_stack.append(new_fmt)
                            self.tag_stack.append(tag)

                        def handle_endtag(self, tag):
                            if tag in self.tag_stack:
                                for i in range(len(self.tag_stack) - 1, -1, -1):
                                    if self.tag_stack[i] == tag:
                                        self.tag_stack.pop(i)
                                        self.format_stack.pop(i + 1)
                                        break

                            if tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'div', 'li']:
                                self._flush_paragraph()
                                self.current_heading = 0
                            elif tag in ['ul', 'ol']:
                                self._flush_paragraph()
                                if self.list_stack:
                                    self.list_stack.pop()
                                if self.ol_counter_stack:
                                    self.ol_counter_stack.pop()
                            elif tag == 'br':
                                self._flush_paragraph()

                        def handle_data(self, data):
                            text = data.replace('\r', '')
                            if not text.strip() and len(self.current_runs) == 0:
                                return
                            fmt = self.format_stack[-1]
                            self.current_runs.append({
                                'text': text,
                                'bold': fmt['bold'],
                                'italic': fmt['italic'],
                                'underline': fmt['underline'],
                                'color': fmt['color'],
                                'highlight': fmt['highlight']
                            })

                    if '<p' not in full_text and '<br' not in full_text and '<div' not in full_text and '<h1' not in full_text and '<ul' not in full_text and '<ol' not in full_text:
                        full_text = full_text.replace('\n', '<br>')
                        
                    parser = DocxHTMLParser()
                    parser.feed(full_text)
                    parser._flush_paragraph()
                    
                    parsed_paragraphs = parser.paragraphs
                    
                    # Save base run properties from the very first run, if any
                    base_rPr = None
                    if paragraph.runs and paragraph.runs[0]._element.rPr is not None:
                        base_rPr = copy.deepcopy(paragraph.runs[0]._element.rPr)
                        
                    # Remove original placeholder runs completely from XML
                    for r_elem in list(paragraph._element.xpath('w:r')):
                        paragraph._element.remove(r_elem)
                        
                    current_p = paragraph
                    
                    for p_data in parsed_paragraphs:
                        if current_p.runs and any(r.text for r in current_p.runs):
                            new_p_element = OxmlElement('w:p')
                            current_p._element.addnext(new_p_element)
                            current_p = Paragraph(new_p_element, current_p._parent)
                            
                        # Clean up inherited pPr properties that might conflict with desired alignment/direction
                        pPr = current_p._element.get_or_add_pPr()
                        for child in list(pPr):
                            if child.tag.endswith(('pStyle', 'jc', 'bidi')):
                                pPr.remove(child)

                        p_dir = p_data.get('direction', 'rtl')
                        p_align = p_data.get('alignment', 'right' if p_dir == 'rtl' else 'left')

                        fmt = current_p.paragraph_format
                        fmt.space_before = Pt(0)
                        fmt.space_after = Pt(0)
                        fmt.line_spacing = 1.0

                        heading_level = p_data.get('heading_level', 0)
                        if heading_level == 1:
                            fmt.space_before = Pt(6)
                            fmt.space_after = Pt(3)
                        elif heading_level == 2:
                            fmt.space_before = Pt(4)
                            fmt.space_after = Pt(2)
                        elif heading_level == 3:
                            fmt.space_before = Pt(3)
                            fmt.space_after = Pt(2)

                        # Set paragraph properties in strict OpenXML schema order:
                        # 1. w:bidi (must be before w:jc and w:rPr)
                        # 2. w:jc
                        # 3. w:rPr
                        p_rPr = pPr.find(qn('w:rPr'))
                        if p_rPr is not None:
                            pPr.remove(p_rPr)

                        bidi = OxmlElement('w:bidi')
                        bidi.set(qn('w:val'), '1' if p_dir == 'rtl' else '0')
                        pPr.append(bidi)

                        jc = OxmlElement('w:jc')
                        jc.set(qn('w:val'), p_align)
                        pPr.append(jc)

                        if p_rPr is not None:
                            pPr.append(p_rPr)
                        
                        for run_info in p_data.get('runs', []):
                            text_part = run_info['text']
                            pieces = re.split(r"(\{\{TABLE_\d+\}\}|\{\{IMAGE_\d+\}\})", text_part)
                            
                            for part in pieces:
                                if not part:
                                    continue
                                    
                                table_match = re.fullmatch(r"\{\{TABLE_(\d+)\}\}", part)
                                if table_match:
                                    if tables_data:
                                        try:
                                            idx = int(table_match.group(1)) - 1
                                            if 0 <= idx < len(tables_data):
                                                t_data = tables_data[idx]
                                                if t_data:
                                                    from docx.enum.table import WD_TABLE_ALIGNMENT
                                                    new_table = doc.add_table(rows=len(t_data), cols=len(t_data[0]))
                                                    
                                                    new_table.autofit = True
                                                    
                                                    try:
                                                        new_table.style = 'Table Grid'
                                                    except:
                                                        pass

                                                    new_table.alignment = WD_TABLE_ALIGNMENT.CENTER
                                                    tblPr = new_table._element.xpath('w:tblPr')
                                                    if tblPr:
                                                        tblW = OxmlElement('w:tblW')
                                                        tblW.set(qn('w:w'), '5000')
                                                        tblW.set(qn('w:type'), 'pct')
                                                        tblPr[0].append(tblW)
                                                        
                                                        bidiVisual = OxmlElement('w:bidiVisual')
                                                        tblPr[0].append(bidiVisual)
                                                        
                                                        tblBorders = OxmlElement('w:tblBorders')
                                                        for border_name in ['top', 'left', 'bottom', 'right', 'insideH', 'insideV']:
                                                            border = OxmlElement(f'w:{border_name}')
                                                            border.set(qn('w:val'), 'single')
                                                            border.set(qn('w:sz'), '4')
                                                            border.set(qn('w:space'), '0')
                                                            border.set(qn('w:color'), '343176')
                                                            tblBorders.append(border)
                                                        tblPr[0].append(tblBorders)

                                                    for r_idx, row_data in enumerate(t_data):
                                                        for c_idx, cell_value in enumerate(row_data):
                                                            cell = new_table.cell(r_idx, c_idx)
                                                            cell.text = ""
                                                            p = cell.paragraphs[0]
                                                            p.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
                                                            pPr = p._element.get_or_add_pPr()
                                                            bidi = OxmlElement('w:bidi')
                                                            bidi.set(qn('w:val'), '1')
                                                            pPr.append(bidi)
                                                            
                                                            run = p.add_run(str(cell_value))
                                                            
                                                            rPr = run._element.get_or_add_rPr()
                                                            rtl = OxmlElement('w:rtl')
                                                            rtl.set(qn('w:val'), '1')
                                                            rPr.append(rtl)
                                                            
                                                            tcPr = cell._element.get_or_add_tcPr()
                                                            shd = OxmlElement('w:shd')
                                                            shd.set(qn('w:val'), 'clear')
                                                            shd.set(qn('w:color'), 'auto')
                                                            
                                                            if r_idx == 0:
                                                                shd.set(qn('w:fill'), '343176')
                                                                run.bold = True
                                                                from docx.shared import RGBColor
                                                                run.font.color.rgb = RGBColor(255, 255, 255)
                                                            else:
                                                                shd.set(qn('w:fill'), 'F4F6F9')
                                                                
                                                            tcPr.append(shd)
                                                    tbl_xml = new_table._element
                                                    tbl_xml.getparent().remove(tbl_xml)
                                                    
                                                    dummy_before_xml = OxmlElement('w:p')
                                                    current_p._element.addnext(dummy_before_xml)
                                                    dummy_before_xml.addnext(tbl_xml)
                                                    
                                                    dummy_p_xml = OxmlElement('w:p')
                                                    tbl_xml.addnext(dummy_p_xml)
                                                    current_p = Paragraph(dummy_p_xml, current_p._parent)
                                                    
                                                    # Re-apply RTL and spacing to the new paragraph
                                                    current_p.alignment = WD_PARAGRAPH_ALIGNMENT.JUSTIFY
                                                    fmt = current_p.paragraph_format
                                                    fmt.space_before = Pt(0)
                                                    fmt.space_after = Pt(0)
                                                    fmt.line_spacing = 1.0
                                                    pPr = current_p._element.get_or_add_pPr()
                                                    bidi = OxmlElement('w:bidi')
                                                    bidi.set(qn('w:val'), '1')
                                                    pPr.append(bidi)
                                        except Exception as e:
                                            print("Table error:", e)
                                    continue
                                    
                                img_match = re.fullmatch(r"\{\{IMAGE_(\d+)\}\}", part)
                                if img_match:
                                    if image_paths:
                                        try:
                                            idx = int(img_match.group(1)) - 1
                                            if 0 <= idx < len(image_paths):
                                                img_path = image_paths[idx]
                                                if img_path and os.path.exists(img_path):
                                                    from docx.shared import Inches
                                                    w_in = 1.0
                                                    h_in = 1.0
                                                    if image_sizes and idx < len(image_sizes) and isinstance(image_sizes[idx], dict):
                                                        try:
                                                            w_in = float(image_sizes[idx].get('width') or 1.0)
                                                        except (ValueError, TypeError):
                                                            w_in = 1.0
                                                        try:
                                                            h_in = float(image_sizes[idx].get('height') or 1.0)
                                                        except (ValueError, TypeError):
                                                            h_in = 1.0
                                                    
                                                    img_p_xml = OxmlElement('w:p')
                                                    current_p._element.addnext(img_p_xml)
                                                    img_p = Paragraph(img_p_xml, current_p._parent)
                                                    
                                                    # Keep alignment of the image paragraph
                                                    if p_align == 'center':
                                                        img_p.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
                                                    elif p_align == 'left':
                                                        img_p.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
                                                    else:
                                                        img_p.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

                                                    run = img_p.add_run()
                                                    if w_in > 0 and h_in > 0:
                                                        run.add_picture(img_path, width=Inches(w_in), height=Inches(h_in))
                                                    elif w_in > 0:
                                                        run.add_picture(img_path, width=Inches(w_in))
                                                    else:
                                                        run.add_picture(img_path, width=Inches(1.0), height=Inches(1.0))
                                                    
                                                    dummy_p_xml = OxmlElement('w:p')
                                                    img_p_xml.addnext(dummy_p_xml)
                                                    current_p = Paragraph(dummy_p_xml, current_p._parent)
                                                    
                                                    # Re-apply alignment and RTL to the following paragraph
                                                    if p_align == 'center':
                                                        current_p.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
                                                    elif p_align == 'left':
                                                        current_p.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
                                                    elif p_align == 'justify':
                                                        current_p.alignment = WD_PARAGRAPH_ALIGNMENT.JUSTIFY
                                                    else:
                                                        current_p.alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT

                                                    fmt = current_p.paragraph_format
                                                    fmt.space_before = Pt(0)
                                                    fmt.space_after = Pt(0)
                                                    fmt.line_spacing = 1.0
                                                    pPr = current_p._element.get_or_add_pPr()
                                                    bidi = OxmlElement('w:bidi')
                                                    bidi.set(qn('w:val'), '1' if p_dir == 'rtl' else '0')
                                                    pPr.append(bidi)
                                        except Exception as e:
                                            print("Image error:", e)
                                    continue
                                    
                                run = current_p.add_run()
                                if base_rPr is not None:
                                    cloned_rPr = copy.deepcopy(base_rPr)
                                    for child in list(cloned_rPr):
                                        if 'textFill' in child.tag:
                                            cloned_rPr.remove(child)
                                        elif child.tag.endswith(('rtl', 'lang')):
                                            cloned_rPr.remove(child)
                                    run._element.insert(0, cloned_rPr)
                                    
                                rPr = run._element.get_or_add_rPr()
                                for child in list(rPr):
                                    if child.tag.endswith(('rtl', 'lang')):
                                        rPr.remove(child)
                                rtl = OxmlElement('w:rtl')
                                rtl.set(qn('w:val'), '1' if p_dir == 'rtl' else '0')
                                rPr.append(rtl)
                                lang = OxmlElement('w:lang')
                                if p_dir == 'rtl':
                                    lang.set(qn('w:bidi'), 'ar-SA')
                                    lang.set(qn('w:val'), 'ar-SA')
                                else:
                                    lang.set(qn('w:val'), 'en-US')
                                rPr.append(lang)
                                
                                if heading_level == 1:
                                    run.bold = True
                                    run.font.size = Pt(16)
                                    from docx.shared import RGBColor
                                    if run_info.get('color'):
                                        r, g, b = run_info['color']
                                        run.font.color.rgb = RGBColor(r, g, b)
                                    else:
                                        run.font.color.rgb = RGBColor(31, 78, 121)
                                elif heading_level == 2:
                                    run.bold = True
                                    run.font.size = Pt(14)
                                    from docx.shared import RGBColor
                                    if run_info.get('color'):
                                        r, g, b = run_info['color']
                                        run.font.color.rgb = RGBColor(r, g, b)
                                    else:
                                        run.font.color.rgb = RGBColor(31, 78, 121)
                                elif heading_level == 3:
                                    run.bold = True
                                    run.font.size = Pt(12.5)
                                    if run_info.get('color'):
                                        from docx.shared import RGBColor
                                        r, g, b = run_info['color']
                                        run.font.color.rgb = RGBColor(r, g, b)
                                else:
                                    if run_info.get('bold'):
                                        run.bold = True
                                    if run_info.get('italic'):
                                        run.italic = True
                                    if run_info.get('underline'):
                                        run.underline = True
                                    if run_info.get('color'):
                                        from docx.shared import RGBColor
                                        r, g, b = run_info['color']
                                        run.font.color.rgb = RGBColor(r, g, b)

                                if run_info.get('highlight'):
                                    existing_hl = rPr.find(qn('w:highlight'))
                                    if existing_hl is not None:
                                        existing_hl.set(qn('w:val'), run_info['highlight'])
                                    else:
                                        hl = OxmlElement('w:highlight')
                                        hl.set(qn('w:val'), run_info['highlight'])
                                        rPr.append(hl)

                                run.text = part
                    
                else:
                    # Normal replacement without paragraph splitting
                    saved_alignment = paragraph.alignment
                    paragraph.runs[0].text = full_text
                    for run in paragraph.runs[1:]:
                        run.text = ""
                    if saved_alignment is not None:
                        paragraph.alignment = saved_alignment

    def _replace_in_t(table):
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    _replace_in_p(paragraph)
                for nested_table in cell.tables:
                    _replace_in_t(nested_table)

    def _replace_in_hf(section_part):
        if section_part is None:
            return
        for paragraph in section_part.paragraphs:
            _replace_in_p(paragraph)
        for table in section_part.tables:
            _replace_in_t(table)

    # If employee is sender, remove manager signature paragraphs
    if remove_manager_sig:
        manager_texts = [
            "مدير مركز الخدمات الإلكترونية",
            "محمد كمال عبد السلام",
            "وكيل كلية الهندسة",
            "وكيل كلية الهندسة لخدمة المجتمع",
            "رئيس قسم هندسة الذكاء الاصطناعي",
            "رئيس قسم هندسة الذكاء الاصطناعى",
            "رئيس قسم الهندسة الطبية الحيوية",
            os.environ.get("SYSTEM_MANAGER_SIG", ""),
            os.environ.get("SYSTEM_MANAGER_NAME", "")
        ]
        manager_texts = [m for m in manager_texts if m]
        # Also include prefixed versions
        manager_texts += [f"و{m}" for m in list(manager_texts)]

        def _remove_manager_p(p):
            text = p.text
            if any(m_text in text for m_text in manager_texts):
                p._element.getparent().remove(p._element)

        for p in doc.paragraphs:
            _remove_manager_p(p)

        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        _remove_manager_p(p)
                    for nested_table in cell.tables:
                        for nested_row in nested_table.rows:
                            for nested_cell in nested_row.cells:
                                for nested_p in nested_cell.paragraphs:
                                    _remove_manager_p(nested_p)

    for paragraph in doc.paragraphs:
        _replace_in_p(paragraph)
    for table in doc.tables:
        _replace_in_t(table)
    for section in doc.sections:
        _replace_in_hf(section.header)
        _replace_in_hf(section.footer)
        _replace_in_hf(section.even_page_header)
        _replace_in_hf(section.even_page_footer)
        _replace_in_hf(section.first_page_header)
        _replace_in_hf(section.first_page_footer)

    doc.save(output_path)


def clean_bidi(text: str) -> str:
    """Remove Unicode directional marks and clean text."""
    if not text:
        return ""
    return re.sub(r'[\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff]', '', text).strip()


def normalize_label(text: str) -> str:
    """Normalize Arabic text for reliable label matching."""
    cleaned = clean_bidi(text)
    cleaned = re.sub(r'[\u0640]', '', cleaned)
    cleaned = re.sub(r'[:\-—/\\.]', ' ', cleaned)
    cleaned = re.sub(r'[إأآا]', 'ا', cleaned)
    cleaned = re.sub(r'[ة]', 'ه', cleaned)
    cleaned = re.sub(r'[ى]', 'ي', cleaned)
    return re.sub(r'\s+', ' ', cleaned).strip().lower()


def is_placeholder(val: str) -> bool:
    """Check if value is a meaningless placeholder returned by AI or empty."""
    if not val:
        return True
    norm = normalize_label(val)
    placeholders = {
        'غير مذكور', 'غير محدد', 'غير معرف', 'لا يوجد', 'بدون', 'لايوجد',
        'none', 'null', 'n/a', 'not specified', 'not mentioned', '-', '--', '...', 'مجهول'
    }
    return norm in placeholders or any(p == norm for p in placeholders)


def extract_document_details(file_or_path, user_email: str = None, default_sender: str = ""):
    """
    Extract structured fields and tables from a Word document (.docx).
    Works for official templates (e.g. ESSIC, AIE, Vice Dean) and external documents.
    Extracts:
      - sender (الراسل)
      - recipient (المرسل إليه)
      - subject (الموضوع)
      - holder_name (عناية ...)
      - position (الصفة)
      - full_body (النص المجرد)
      - full_body_html (النص بتنسيق الألوان والفقرات)
      - tables_data (الجداول غير الترويسية/التوقيعية)
    """
    import html
    import logging
    logger = logging.getLogger(__name__)

    if hasattr(file_or_path, 'seek'):
        file_or_path.seek(0)

    doc = Document(file_or_path)

    fields = {
        'sender': '',
        'recipient': '',
        'subject': '',
        'holder_name': '',
        'position': '',
        'full_body': '',
        'full_body_html': ''
    }
    tables_data = []

    # 1. Inspect tables
    for t_idx, table in enumerate(doc.tables):
        is_metadata_table = False
        is_signature_table = False
        is_logo_table = (t_idx == 0 and len(table.rows) <= 2 and len(table.columns) <= 3)

        # Signature check
        for row in table.rows:
            for c in row.cells:
                norm_c = normalize_label(c.text)
                if any(k in norm_c for k in ['رئيس قسم', 'وكيل كليه', 'مدير مركز', 'عميد الكليه', 'محمد كمال عبد السلام', 'مقدمه لسيادتكم']):
                    is_signature_table = True
                    break
            if is_signature_table:
                break

        # Metadata table check (col 0 = value, col 1 = label OR vice versa)
        for row in table.rows:
            cell_texts = [clean_bidi(c.text) for c in row.cells]
            if len(row.cells) >= 2:
                c0_norm = normalize_label(cell_texts[0])
                c1_norm = normalize_label(cell_texts[1])

                label_cell = None
                val_cell = None

                if any(k in c1_norm for k in ['راسل', 'مرسل', 'موضوع', 'شان', 'عنايه', 'صفه', 'منصب', 'وظيفه']):
                    label_cell = c1_norm
                    val_cell = cell_texts[0]
                elif any(k in c0_norm for k in ['راسل', 'مرسل', 'موضوع', 'شان', 'عنايه', 'صفه', 'منصب', 'وظيفه']):
                    label_cell = c0_norm
                    val_cell = ' '.join(cell_texts[1:])

                if label_cell and val_cell:
                    is_metadata_table = True
                    # Check recipient before sender because "المرسل إليه" contains "المرسل"
                    if 'مرسل اليه' in label_cell or ('مرسل' in label_cell and 'الي' in label_cell) or label_cell == 'الي':
                        if not fields['recipient']:
                            fields['recipient'] = val_cell
                    elif 'راسل' in label_cell or ('مرسل' in label_cell and 'الي' not in label_cell):
                        if not fields['sender']:
                            fields['sender'] = val_cell
                    elif 'موضوع' in label_cell or 'شان' in label_cell:
                        if not fields['subject']:
                            fields['subject'] = val_cell
                    elif 'عنايه' in label_cell:
                        if not fields['holder_name']:
                            fields['holder_name'] = val_cell
                    elif any(k in label_cell for k in ['صفه', 'منصب', 'وظيفه']):
                        if not fields['position']:
                            fields['position'] = val_cell

        if not is_metadata_table and not is_signature_table and not is_logo_table:
            tbl_rows = []
            for row in table.rows:
                row_vals = [clean_bidi(c.text) for c in row.cells]
                if any(row_vals):
                    tbl_rows.append(row_vals)
            if tbl_rows:
                tables_data.append(tbl_rows)

    # 2. Inspect paragraphs
    body_paragraphs_plain = []
    body_paragraphs_html = []
    found_greeting = False
    passed_header = False

    for p in doc.paragraphs:
        txt = clean_bidi(p.text)
        if not txt:
            continue
        clean_line = re.sub(r'[\u0640]', '', txt)
        norm_txt = normalize_label(txt)

        # Skip Ref / Code line
        if re.search(r'(?:ref|code)\s*no\s*[:.]?', norm_txt, re.IGNORECASE) or norm_txt.startswith('ref no') or norm_txt.startswith('code no'):
            continue

        # Check inline label: value
        m_recip = re.match(r'^(?:المرسل\s*إليه|المرسل\s*اليه|إلى|إلي)\s*[:\-]\s*(.*)$', clean_line)
        if m_recip and not fields['recipient']:
            fields['recipient'] = clean_bidi(m_recip.group(1))
            continue

        m_sender = re.match(r'^(?:الراسل|المرسل)\s*[:\-]\s*(.*)$', clean_line)
        if m_sender and not fields['sender']:
            fields['sender'] = clean_bidi(m_sender.group(1))
            continue

        m_subj = re.match(r'^(?:الموضوع|بشأن|بخصوص)\s*[:\-]\s*(.*)$', clean_line)
        if m_subj and not fields['subject']:
            fields['subject'] = clean_bidi(m_subj.group(1))
            continue

        # Check عناية
        if 'عنايه' in norm_txt:
            passed_header = True
            m_holder = re.search(r'عناي[هة]\s*(?:السيد(?:\s*الاستاذ)?(?:\s*الدكتور)?\s*[/:\-]?\s*)?(.*)', clean_line)
            if m_holder and not fields['holder_name']:
                fields['holder_name'] = clean_bidi(m_holder.group(1))
            continue

        # Check greeting
        if 'تحيه طيبه وبعد' in norm_txt:
            found_greeting = True
            passed_header = True
            continue

        # Check sign-offs
        if any(s in norm_txt for s in ['وتفضلوا بقبول', 'فائق الاحترام', 'مع وافر الاحترام', 'شاكرين لسيادتكم', 'شاكرين حسن تعاونكم']):
            break

        # Check signatures
        if any(s in norm_txt for s in ['مدير مركز', 'وكيل كليه', 'رئيس قسم', 'محمد كمال عبد السلام', 'مقدمه لسيادتكم']):
            break

        # Position line under عناية before greeting
        if passed_header and not found_greeting and not fields['position']:
            if len(txt.split()) <= 6 and any(pos in norm_txt for pos in ['استاذ', 'عميد', 'وكيل', 'رئيس', 'مدير', 'مهندس', 'دكتور', 'مدرس']):
                fields['position'] = txt
                continue

        # Body paragraphs
        if found_greeting or passed_header:
            body_paragraphs_plain.append(txt)
            p_runs_html = []
            for run in p.runs:
                r_txt = clean_bidi(run.text)
                if not r_txt:
                    continue
                escaped = html.escape(r_txt)
                color_hex = None
                if run.font and run.font.color and run.font.color.rgb:
                    color_hex = f'#{run.font.color.rgb}'

                style_parts = []
                if color_hex:
                    style_parts.append(f'color:{color_hex}')

                run_tag = escaped
                if style_parts:
                    run_tag = f'<span style="{";".join(style_parts)}">{run_tag}</span>'
                if run.bold:
                    run_tag = f'<strong>{run_tag}</strong>'
                if run.italic:
                    run_tag = f'<em>{run_tag}</em>'
                if run.underline:
                    run_tag = f'<u>{run_tag}</u>'
                p_runs_html.append(run_tag)

            if p_runs_html:
                body_paragraphs_html.append(f'<p dir="rtl" style="text-align: right;">{"".join(p_runs_html)}</p>')
            else:
                body_paragraphs_html.append(f'<p dir="rtl" style="text-align: right;">{html.escape(txt)}</p>')

    # 3. Clean placeholders from initial extraction
    for k in fields:
        if is_placeholder(fields[k]):
            fields[k] = ''

    # 4. If key fields or body are missing (unstructured document), fall back to AI
    if not fields['recipient'] or not fields['subject'] or not body_paragraphs_plain:
        try:
            full_text_parts = []
            for ti, table in enumerate(doc.tables):
                t_lines = []
                for row in table.rows:
                    row_str = " | ".join(clean_bidi(c.text) for c in row.cells if clean_bidi(c.text))
                    if row_str:
                        t_lines.append(row_str)
                if t_lines:
                    full_text_parts.append("\n".join(t_lines))

            for p in doc.paragraphs:
                pt = clean_bidi(p.text)
                if pt:
                    full_text_parts.append(pt)

            combined_text = "\n\n".join(full_text_parts)
            if combined_text.strip():
                from services.ai_generator import extract_document_fields
                ai_fields = extract_document_fields(combined_text, user_email or "")
                if ai_fields and isinstance(ai_fields, dict):
                    for k in ["recipient", "subject", "holder_name", "position", "sender", "full_body"]:
                        val = ai_fields.get(k, "")
                        if not fields.get(k) and val and not is_placeholder(val):
                            fields[k] = val
        except Exception as ai_err:
            logger.warning(f"AI fallback extraction failed: {ai_err}")

    # 5. Final fallback assignments
    if not fields['full_body'] and body_paragraphs_plain:
        fields['full_body'] = '\n'.join(body_paragraphs_plain)

    if not fields['full_body_html'] and body_paragraphs_html:
        fields['full_body_html'] = ''.join(body_paragraphs_html)

    if fields['full_body'] and not fields['full_body_html']:
        fields['full_body_html'] = ''.join(f'<p dir="rtl" style="text-align: right;">{html.escape(l)}</p>' for l in fields['full_body'].split('\n') if l.strip())

    if not fields['sender'] and default_sender and not is_placeholder(default_sender):
        fields['sender'] = default_sender

    for k in fields:
        if is_placeholder(fields[k]):
            fields[k] = ''

    return fields, tables_data