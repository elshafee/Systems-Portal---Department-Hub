import os
import glob

def patch_templates():
    template_dir = 'core_app/templates'
    html_files = glob.glob(os.path.join(template_dir, '*.html'))
    
    for filepath in html_files:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace only the exact uppercase 'ESSIC'
        # Skip 'template_essic.docx' and 'essic-loader' and 'essic_bg.jpg' since they are lowercase.
        new_content = content.replace('ESSIC', '{{ SYSTEM_OFFICE_CODE }}')
        
        if new_content != content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"Patched {filepath}")

if __name__ == '__main__':
    patch_templates()
