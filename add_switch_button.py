import sys
import re
import os

def patch_app(app_path):
    # Patch app.py to inject GATEWAY_URL
    app_file = os.path.join(app_path, 'flask', 'app.py')
    with open(app_file, 'r') as f:
        content = f.read()

    # Replace the return dict in inject_globals
    pattern = r"return dict\(is_admin=is_admin,\s*get_word_online_url=get_word_online_url\)"
    replacement = "return dict(is_admin=is_admin, get_word_online_url=get_word_online_url, GATEWAY_URL=GATEWAY_URL)"
    new_content = re.sub(pattern, replacement, content)
    
    with open(app_file, 'w') as f:
        f.write(new_content)

    # Patch base.html
    base_html = os.path.join(app_path, 'flask', 'templates', 'base.html')
    with open(base_html, 'r') as f:
        html_content = f.read()

    switch_btn = """
      <div class="nav-label" style="margin-top:20px;">System</div>
      <a href="{{ GATEWAY_URL }}" style="color: #2e8de4; font-weight: 600; background: rgba(46, 141, 228, 0.05); border: 1px solid rgba(46, 141, 228, 0.2); border-radius: 8px; margin-top: 5px; transition: all 0.2s;" onmouseover="this.style.background='rgba(46, 141, 228, 0.15)'" onmouseout="this.style.background='rgba(46, 141, 228, 0.05)'">
        <i class="bi bi-grid-3x3-gap-fill"></i> Switch System
      </a>
    </nav>"""
    
    if "Switch System" not in html_content:
        html_content = html_content.replace('    </nav>', switch_btn)
        with open(base_html, 'w') as f:
            f.write(html_content)

if __name__ == '__main__':
    apps = ['Essic', 'Faculty-of-engineering-documenting', 'biomedical_department']
    for app in apps:
        patch_app(app)
        print(f"Patched {app}")
