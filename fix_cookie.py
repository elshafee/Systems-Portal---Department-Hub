import sys
import os
import re

def fix_cookie_name(app_path, cookie_name):
    app_file = os.path.join(app_path, 'flask', 'app.py')
    with open(app_file, 'r') as f:
        content = f.read()

    # Add the config if it's not already there
    if 'SESSION_COOKIE_NAME' not in content:
        # Find where app is defined
        pattern = r"(app = Flask\(__name__\).*?\n)(.*?)"
        # We will just insert it after app = Flask(__name__) or after app.config['...']
        # Let's insert it right after app.secret_key
        
        replacement = f"\\1app.config['SESSION_COOKIE_NAME'] = '{cookie_name}'\n\\2"
        content = re.sub(pattern, replacement, content, count=1)
        
        with open(app_file, 'w') as f:
            f.write(content)

if __name__ == '__main__':
    fix_cookie_name('Essic', 'essic_session')
    fix_cookie_name('Faculty-of-engineering-documenting', 'faculty_session')
    fix_cookie_name('biomedical_department', 'biomedical_session')
    print("Cookie names fixed.")
