import os
import subprocess
import shutil

# Common LibreOffice paths on macOS / Linux
SOFFICE_PATHS = [
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    "/usr/bin/soffice",
    "/usr/local/bin/soffice",
    shutil.which("soffice") or "",
]


def convert_docx_to_pdf(docx_path, pdf_path):
    """
    Converts a DOCX file to PDF using LibreOffice in headless mode.
    Returns True if successful, False otherwise.
    """
    if not os.path.exists(docx_path):
        print(f"DOCX not found at {docx_path}")
        return False

    soffice = None
    for path in SOFFICE_PATHS:
        if path and os.path.isfile(path):
            soffice = path
            break

    if not soffice:
        print("LibreOffice not found on this system.")
        return False

    try:
        out_dir = os.path.dirname(pdf_path) or "."
        # Use an isolated user profile to prevent conflicts with a running
        # LibreOffice instance and fix the macOS /var → /private/var symlink issue.
        user_prof = f"-env:UserInstallation=file://{os.path.realpath(out_dir)}/lo_profile"

        result = subprocess.run(
            [
                soffice,
                user_prof,
                "--headless",
                "--convert-to", "pdf",
                "--outdir", out_dir,
                docx_path,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            print(f"LibreOffice error: {result.stderr}")
            shutil.rmtree(os.path.join(out_dir, "lo_profile"), ignore_errors=True)
            return False

        # LibreOffice names the output after the input file's stem.
        stem = os.path.splitext(os.path.basename(docx_path))[0]
        # Use realpath to resolve macOS symlinks (/var/folders → /private/var/folders)
        real_out_dir = os.path.realpath(out_dir)
        lo_output = os.path.join(real_out_dir, f"{stem}.pdf")

        if os.path.exists(lo_output):
            if os.path.realpath(lo_output) != os.path.realpath(pdf_path):
                shutil.move(lo_output, pdf_path)
            shutil.rmtree(os.path.join(out_dir, "lo_profile"), ignore_errors=True)
            return True

        print("LibreOffice ran but the output PDF was not found.")
        shutil.rmtree(os.path.join(out_dir, "lo_profile"), ignore_errors=True)
        return False

    except Exception as e:
        print(f"LibreOffice conversion failed: {e}")
        shutil.rmtree(os.path.join(out_dir, "lo_profile"), ignore_errors=True)
        return False