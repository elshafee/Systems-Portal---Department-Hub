import sys
import re

def patch_app(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # Add import jwt if not there
    if 'import jwt' not in content:
        content = content.replace('import os\n', 'import os\nimport jwt\n')
        
    # Replace login_required
    new_login_required = '''
GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://localhost:5000")
SSO_SECRET = os.environ.get("SSO_SECRET", "shared_sso_secret_key_12345_32bytes_long")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            # Need to encode the return URL? 
            # In a real app we'd pass ?next=request.url
            return redirect(f"{GATEWAY_URL}/login")
        return f(*args, **kwargs)

    return decorated_function
'''
    content = re.sub(
        r'def login_required\(f\):.*?return decorated_function',
        new_login_required.strip(),
        content,
        flags=re.DOTALL
    )

    sso_route = '''
@app.route('/sso_login')
def sso_login():
    token = request.args.get('token')
    next_url = request.args.get('next')
    if not token:
        return redirect(f"{GATEWAY_URL}/login")
    try:
        data = jwt.decode(token, SSO_SECRET, algorithms=["HS256"])
        session['user'] = {'name': data.get('name', ''), 'email': data['email']}
        if next_url:
            return redirect(next_url)
        return redirect(url_for('index'))
    except Exception as e:
        return f"SSO Error: {e}", 400

@app.route('/login', methods=['GET', 'POST'])
'''
    # Insert before login
    content = content.replace("@app.route('/login', methods=['GET', 'POST'])", sso_route)

    # Disable the old routes by returning redirect to Gateway
    for old_route in ['login', 'setup', 'verify']:
        pattern = rf"(@app\.route\('/{old_route}'.*?def {old_route}\(\):).*?(?=\n@app\.route)"
        replacement = rf"\1\n    return redirect(f'{{GATEWAY_URL}}/{old_route}')\n"
        content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        
    # Logout route
    logout_pattern = r"(@app\.route\('/logout'\).*?def logout\(\):).*?(?=\n@app\.route)"
    logout_replacement = r"\1\n    session.pop('user', None)\n    return redirect(f'{GATEWAY_URL}/logout')\n"
    content = re.sub(logout_pattern, logout_replacement, content, flags=re.DOTALL)

    with open(filepath, 'w') as f:
        f.write(content)

if __name__ == '__main__':
    for p in sys.argv[1:]:
        patch_app(p)
        print(f"Patched {p}")
