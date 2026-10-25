import tempfile
import os
import subprocess

def test_libre():
    out_dir = tempfile.mkdtemp()
    docx_path = "template_essic.docx"
    soffice = "/Applications/LibreOffice.app/Contents/MacOS/soffice"
    user_prof = f"-env:UserInstallation=file://{out_dir}/lo_profile"
    
    cmd = [
        soffice,
        user_prof,
        "--headless",
        "--convert-to", "pdf",
        "--outdir", out_dir,
        docx_path
    ]
    print("Running:", " ".join(cmd))
    res = subprocess.run(cmd, capture_output=True, text=True)
    print("Code:", res.returncode)
    print("Stdout:", res.stdout)
    print("Stderr:", res.stderr)
    print("Files:", os.listdir(out_dir))

test_libre()
