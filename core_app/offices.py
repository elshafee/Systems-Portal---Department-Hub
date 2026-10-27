"""
core_app/offices.py
Central registry of departments/offices configuration.
Provides seamless switching between ESSIC, Vice Dean (HUEED), and Artificial Engineering (AIE).
"""
import os
from flask import session

OFFICE_CONFIGS = {
    'ESSIC': {
        'code': 'ESSIC',
        'name': 'مركز الخدمات الإلكترونية',
        'name_en': 'ESSIC Center',
        'org_name': 'مدير مركز الخدمات الإلكترونية',
        'org_example': 'كلية الهندسة',
        'manager_title': 'مدير مركز الخدمات الإلكترونية والإبداع العلمي',
        'manager_sig': 'مدير مركز الخدمات الإلكترونية',
        'manager_name': 'محمد كمال عبد السلام',
        'template': 'template_essic.docx',
        'preview_bg': 'assets/doc_image3.png',
        'preview_footer': 'assets/image4.png',
        'preview_pt': '18%',
        'known_abbrs': 'ESSIC,HUE,IT,HR',
        'onedrive_folder': '/personal/aelshafee_horus_edu_eg/Documents/ESSIC_Docs',
        'color': '#2e8de4',
        'icon': 'bi-building-fill-gear'
    },
    'HUEED': {
        'code': 'HUEED',
        'name': 'وكيل كلية الهندسة',
        'name_en': 'Vice Dean (Engineering)',
        'org_name': 'وكيل كلية الهندسة',
        'org_example': 'وكيل كلية الهندسة',
        'manager_title': 'وكيل كلية الهندسة لخدمة المجتمع و شئون البيئة',
        'manager_sig': 'وكيل كلية الهندسة لخدمة المجتمع و شئون البيئة',
        'manager_name': 'محمد كمال عبد السلام',
        'template': 'template_vice_dean.docx',
        'preview_bg': 'assets/vice_dean_bg.png',
        'preview_footer': 'assets/blank.png',
        'preview_pt': '28%',
        'known_abbrs': 'Faculty of Engineering Vice Dean,HUE,IT,HR',
        'onedrive_folder': '/personal/aelshafee_horus_edu_eg/Documents/Faculty_of_Engineering_Docs',
        'color': '#198754',
        'icon': 'bi-bank2'
    },
    'AIE': {
        'code': 'AIE',
        'name': 'قسم هندسة الذكاء الاصطناعي',
        'name_en': 'Artificial Engineering (AIE)',
        'org_name': 'رئيس قسم هندسة الذكاء الاصطناعي',
        'org_example': 'كلية الهندسة',
        'manager_title': 'رئيس قسم هندسة الذكاء الاصطناعى – كلية الهندسة',
        'manager_sig': 'رئيس قسم هندسة الذكاء الاصطناعى',
        'manager_name': 'محمد كمال عبد السلام',
        'template': 'template_aie.docx',
        'preview_bg': 'assets/aie_bg.png',
        'preview_footer': 'assets/blank.png',
        'preview_pt': '28%',
        'known_abbrs': 'ESSIC,HUE,IT,HR,AIE',
        'onedrive_folder': '/personal/aelshafee_horus_edu_eg/Documents/AIE_Docs',
        'color': '#0dcaf0',
        'icon': 'bi-cpu-fill'
    }
}

DEFAULT_OFFICE = os.environ.get("SYSTEM_OFFICE_CODE", "ESSIC")

def get_current_office() -> dict:
    code = session.get('active_office', DEFAULT_OFFICE).upper()
    if code not in OFFICE_CONFIGS:
        code = DEFAULT_OFFICE if DEFAULT_OFFICE in OFFICE_CONFIGS else 'ESSIC'
    return OFFICE_CONFIGS[code]

def get_office_by_code(code: str) -> dict:
    if not code:
        return OFFICE_CONFIGS.get('ESSIC')
    return OFFICE_CONFIGS.get(code.upper(), OFFICE_CONFIGS.get('ESSIC'))

def set_current_office(code: str) -> bool:
    code = code.upper()
    if code in OFFICE_CONFIGS:
        session['active_office'] = code
        return True
    return False
