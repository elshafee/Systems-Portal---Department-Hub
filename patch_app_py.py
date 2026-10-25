import os
import re

def patch_app_py():
    filepath = 'core_app/app.py'
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Insert global variable
    if 'SYSTEM_TEMPLATE_FILENAME =' not in content:
        content = content.replace(
            'SSO_SECRET = os.environ.get("SSO_SECRET", "shared_sso_secret_key_12345_32bytes_long")',
            'SSO_SECRET = os.environ.get("SSO_SECRET", "shared_sso_secret_key_12345_32bytes_long")\nSYSTEM_TEMPLATE_FILENAME = os.environ.get("SYSTEM_TEMPLATE_FILENAME", "template_essic.docx")\nSYSTEM_TEMPLATE_STEM = SYSTEM_TEMPLATE_FILENAME.rsplit(".", 1)[0]'
        )
    
    # 2. Replace hardcoded string "template_essic.docx" with SYSTEM_TEMPLATE_FILENAME
    content = content.replace('"template_essic.docx"', 'SYSTEM_TEMPLATE_FILENAME')
    content = content.replace("'template_essic.docx'", 'SYSTEM_TEMPLATE_FILENAME')
    
    # 3. Replace "Default template (template_essic.docx) not found."
    content = content.replace('flash("Default template (template_essic.docx) not found.", "danger")', 'flash(f"Default template ({SYSTEM_TEMPLATE_FILENAME}) not found.", "danger")')
    content = content.replace("flash('Default template (template_essic.docx) not found.', 'danger')", 'flash(f"Default template ({SYSTEM_TEMPLATE_FILENAME}) not found.", "danger")')
    
    # 4. Replace hardcoded stem "template_essic"
    content = content.replace('"template_essic"', 'SYSTEM_TEMPLATE_STEM')
    content = content.replace("'template_essic'", 'SYSTEM_TEMPLATE_STEM')

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched app.py successfully.")

if __name__ == '__main__':
    patch_app_py()
