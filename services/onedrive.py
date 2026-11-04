"""
services/onedrive.py

Handles OneDrive/SharePoint interactions using Guest Cookies via requests.
Supports department-level folder classification (ESSIC, CSED, AIE)
for both official documents and preview documents.
"""
import os
import requests
import urllib.parse
import re

LAST_ERROR = ""


def extract_office_code_from_filename(filename: str) -> str:
    """Extract office/department code from a filename if present."""
    if not filename:
        return None
    fn = filename.upper()
    if any(k in fn for k in ['CSED', 'ENG.CSED', 'HUEED', 'VICE_DEAN']):
        return 'CSED'
    if 'AIE' in fn:
        return 'AIE'
    if 'ESSIC' in fn:
        return 'ESSIC'
    return None


def get_sharepoint_config(is_preview: bool = False, office_code: str = None):
    """
    Returns share_url, base_url, site_url, folder_path, root_folder, dept
    Classifies target folder by department (ESSIC, CSED, AIE).
    """
    share_url = os.environ.get("ONEDRIVE_SHARE_URL", "").strip('"\'')
    if is_preview:
        share_url = os.environ.get("ONEDRIVE_PREVIEW_SHARE_URL", share_url).strip('"\'')
        
    if not share_url:
        share_url = None
        
    base_url = "https://horusuni-my.sharepoint.com"
    site_url = f"{base_url}/personal/aelshafee_horus_edu_eg"
    
    if is_preview:
        root_folder = "/personal/aelshafee_horus_edu_eg/Documents/previews"
    else:
        root_folder = os.environ.get("SYSTEM_ONEDRIVE_FOLDER", "/personal/aelshafee_horus_edu_eg/Documents/ESSIC_Docs")

    # Determine department code (ESSIC, CSED, AIE)
    dept = None
    if office_code:
        code_upper = str(office_code).upper().strip()
        if code_upper in ('CSED', 'HUEED', 'ENG.CSED', 'VICE_DEAN'):
            dept = 'CSED'
        elif 'AIE' in code_upper:
            dept = 'AIE'
        elif 'ESSIC' in code_upper:
            dept = 'ESSIC'
        else:
            dept = code_upper

    if not dept:
        try:
            from flask import session, has_request_context
            if has_request_context():
                active = session.get('active_office', 'ESSIC').upper()
                dept = 'CSED' if active in ('CSED', 'HUEED') else ('AIE' if active == 'AIE' else 'ESSIC')
        except Exception:
            pass

    if not dept:
        dept = 'ESSIC'

    folder_path = f"{root_folder}/{dept}"
    return share_url, base_url, site_url, folder_path, root_folder, dept


def get_subfolder_from_filename(filename: str) -> str:
    """Extract mm-yyyy subfolder from filename if present (e.g. 11-2026)."""
    if not filename:
        return None
    match = re.search(r'(\d{2}-\d{4})\.(docx|pdf)$', filename, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def upload_file_to_share(local_filepath: str, dest_filename: str, is_preview: bool = False, office_code: str = None) -> bool:
    """
    Uploads a local file to the shared OneDrive folder using Guest Cookies.
    Classifies into department folder:
      - For previews:  previews/{dept}/{dest_filename}
      - For documents: {SYSTEM_ONEDRIVE_FOLDER}/{dept}/{optional_month_year}/{dest_filename}
    Returns True on success, False on failure.
    """
    global LAST_ERROR
    LAST_ERROR = ""
    
    if not office_code:
        office_code = extract_office_code_from_filename(dest_filename)

    share_url, base_url, site_url, folder_path, root_folder, dept = get_sharepoint_config(is_preview, office_code)
    
    if not share_url:
        LAST_ERROR = "ONEDRIVE_SHARE_URL not configured."
        print(f"[Upload Error] {LAST_ERROR}")
        return False
        
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36'
    })

    try:
        # STEP 1: Fetch guest cookies
        initial_response = session.get(share_url)
        initial_response.raise_for_status()

        # STEP 2: Generate fresh x-requestdigest token
        context_info_url = f"{site_url}/_api/contextinfo"
        ctx_headers = {
            'Accept': 'application/json;odata=verbose',
            'Content-Type': 'application/json;odata=verbose'
        }
        ctx_response = session.post(context_info_url, headers=ctx_headers)
        if ctx_response.status_code != 200:
            LAST_ERROR = f"Failed to get authorization token: {ctx_response.text}"
            print(f"[Upload Error] {LAST_ERROR}")
            return False

        request_digest = ctx_response.json()['d']['GetContextWebInformation']['FormDigestValue']

        # Ensure department folder exists under root_folder
        encoded_root = urllib.parse.quote(root_folder, safe='')
        create_dept_url = f"{site_url}/_api/web/GetFolderByServerRelativePath(DecodedUrl=@v)/Folders/add('{dept}')?@v=%27{encoded_root}%27"
        create_headers = {
            'Accept': 'application/json;odata=verbose',
            'Content-Type': 'application/json;odata=verbose',
            'X-RequestDigest': request_digest
        }
        session.post(create_dept_url, headers=create_headers)

        target_folder_path = f"{root_folder}/{dept}"
        
        # For non-preview documents, organize by monthly subfolder (e.g. 11-2026)
        if not is_preview:
            subfolder = get_subfolder_from_filename(dest_filename)
            if subfolder:
                encoded_dept = urllib.parse.quote(target_folder_path, safe='')
                create_sub_url = f"{site_url}/_api/web/GetFolderByServerRelativePath(DecodedUrl=@v)/Folders/add('{subfolder}')?@v=%27{encoded_dept}%27"
                session.post(create_sub_url, headers=create_headers)
                target_folder_path = f"{target_folder_path}/{subfolder}"

        # STEP 3: Upload the File
        encoded_folder = urllib.parse.quote(target_folder_path, safe='')
        encoded_filename = urllib.parse.quote(dest_filename, safe='')

        upload_endpoint = (
            f"{site_url}/_api/web/GetFolderByServerRelativePath(DecodedUrl=@a1)/Files/AddUsingPath"
            f"(DecodedUrl=@a2,Overwrite=@a3)"
            f"?@a1=%27{encoded_folder}%27&@a2=%27{encoded_filename}%27&@a3=true"
        )

        upload_headers = {
            'Accept': 'application/json;odata=verbose',
            'Content-Type': 'application/octet-stream',
            'X-RequestDigest': request_digest
        }

        with open(local_filepath, 'rb') as f:
            upload_response = session.post(upload_endpoint, headers=upload_headers, data=f)

        if upload_response.status_code in [200, 201, 202]:
            return True
        elif upload_response.status_code == 423 or "SPFileLockException" in upload_response.text:
            LAST_ERROR = "The document is currently open in Word Online. Please close the Word Online tab before previewing or generating so the file can be updated."
            print(f"[Upload Error] {LAST_ERROR}")
            return False
        else:
            LAST_ERROR = f"Status {upload_response.status_code}: {upload_response.text}"
            print(f"[Upload Error] {LAST_ERROR}")
            return False
            
    except Exception as e:
        LAST_ERROR = str(e)
        print(f"[Upload Exception] {LAST_ERROR}")
        return False


def delete_file_from_share(target_file_name: str, is_preview: bool = False, office_code: str = None) -> bool:
    """
    Deletes or clears a file from the shared OneDrive folder using Guest Cookies.
    Searches inside the department subfolder as well as root and known depts.
    If SharePoint denies DELETE (HTTP 403 on guest links), truncates the file to 0 bytes
    so no stale content remains.
    """
    if not target_file_name:
        return False

    if not office_code:
        office_code = extract_office_code_from_filename(target_file_name)

    share_url, base_url, site_url, folder_path, root_folder, dept = get_sharepoint_config(is_preview, office_code)
    
    if not share_url:
        return False
        
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36'
    })
    
    try:
        initial_response = session.get(share_url)
        initial_response.raise_for_status()

        context_info_url = f"{site_url}/_api/contextinfo"
        ctx_headers = {
            'Accept': 'application/json;odata=verbose',
            'Content-Type': 'application/json;odata=verbose'
        }
        ctx_response = session.post(context_info_url, headers=ctx_headers)
        if ctx_response.status_code != 200:
            return False

        request_digest = ctx_response.json()['d']['GetContextWebInformation']['FormDigestValue']

        # Collect candidate folders where this file could reside
        candidate_folders = []
        subfolder = get_subfolder_from_filename(target_file_name) if not is_preview else None
        if subfolder:
            candidate_folders.append(f"{folder_path}/{subfolder}")
        candidate_folders.append(folder_path)

        if is_preview:
            for d in ['ESSIC', 'CSED', 'AIE']:
                candidate_folders.append(f"{root_folder}/{d}")
        elif subfolder:
            candidate_folders.append(f"{root_folder}/{subfolder}")

        candidate_folders.append(root_folder)

        # Unique folders preserving order
        seen = set()
        unique_folders = []
        for cf in candidate_folders:
            if cf not in seen:
                seen.add(cf)
                unique_folders.append(cf)

        success = False
        for c_folder in unique_folders:
            file_path = f"{c_folder}/{target_file_name}"
            encoded_file_path = urllib.parse.quote(file_path, safe='')
            
            delete_endpoint = (
                f"{site_url}/_api/web/GetFileByServerRelativePath(DecodedUrl=@v)"
                f"?@v=%27{encoded_file_path}%27"
            )
            
            delete_headers = {
                'Accept': 'application/json;odata=verbose',
                'X-RequestDigest': request_digest,
                'IF-MATCH': '*',
                'X-HTTP-Method': 'DELETE'
            }
            
            delete_response = session.post(delete_endpoint, headers=delete_headers)
            if delete_response.status_code in [200, 204]:
                success = True
            elif delete_response.status_code == 403:
                # Guest cookies lack DELETE permissions on SharePoint.
                # Truncate/clear the file so no stale data remains.
                encoded_folder = urllib.parse.quote(c_folder, safe='')
                encoded_filename = urllib.parse.quote(target_file_name, safe='')
                clear_endpoint = (
                    f"{site_url}/_api/web/GetFolderByServerRelativePath(DecodedUrl=@a1)/Files/AddUsingPath"
                    f"(DecodedUrl=@a2,Overwrite=@a3)"
                    f"?@a1=%27{encoded_folder}%27&@a2=%27{encoded_filename}%27&@a3=true"
                )
                clear_headers = {
                    'Accept': 'application/json;odata=verbose',
                    'Content-Type': 'application/octet-stream',
                    'X-RequestDigest': request_digest
                }
                clear_resp = session.post(clear_endpoint, headers=clear_headers, data=b"")
                if clear_resp.status_code in [200, 201, 202]:
                    success = True

        return success
    except Exception as e:
        print(f"[Delete Exception] {e}")
        return False


def download_file_from_share(target_file_name: str, local_save_path: str, is_preview: bool = False, office_code: str = None) -> bool:
    """
    Downloads a file from SharePoint folder using Guest Cookies.
    Checks department folder, falls back to legacy root folder if needed.
    """
    if not office_code:
        office_code = extract_office_code_from_filename(target_file_name)

    share_url, base_url, site_url, folder_path, root_folder, dept = get_sharepoint_config(is_preview, office_code)
    
    if not share_url:
        print("[Download Error] ONEDRIVE_SHARE_URL not configured.")
        return False
        
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5'
    })
    
    try:
        response = session.get(share_url)
        if 'FedAuth' not in session.cookies:
            print("[Download Error] The FedAuth cookie was not set. Check your sharing link.")
            return False

        candidate_folders = []
        subfolder = get_subfolder_from_filename(target_file_name) if not is_preview else None
        if subfolder:
            candidate_folders.append(f"{folder_path}/{subfolder}")
        candidate_folders.append(folder_path)
        if subfolder:
            candidate_folders.append(f"{root_folder}/{subfolder}")
        candidate_folders.append(root_folder)

        seen = set()
        unique_folders = [cf for cf in candidate_folders if not (cf in seen or seen.add(cf))]

        for c_folder in unique_folders:
            file_path = f"{c_folder}/{target_file_name}"
            encoded_file_path = urllib.parse.quote(file_path, safe='')
            
            download_endpoint = (
                f"{site_url}/_api/web/GetFileByServerRelativePath(DecodedUrl=@v)/$value"
                f"?@v=%27{encoded_file_path}%27"
            )

            download_response = session.get(download_endpoint, stream=True)
            if download_response.status_code == 200:
                with open(local_save_path, 'wb') as f:
                    for chunk in download_response.iter_content(chunk_size=8192):
                        f.write(chunk)
                return True

        return False
    except Exception as e:
        print(f"[Download Exception] {e}")
        return False


upload_file_to_onedrive = upload_file_to_share


def get_word_online_url(filename: str, is_preview: bool = False, action: str = None, office_code: str = None) -> str:
    """
    Returns the direct Word Online (SharePoint viewer) URL for a given filename.
    Resolves the exact department folder (e.g. previews/CSED/Preview_xxx.docx).
    For previews, defaults to action='edit' so the document can be edited directly.
    """
    if not office_code:
        office_code = extract_office_code_from_filename(filename)

    _, base_url, site_url, folder_path, root_folder, dept = get_sharepoint_config(is_preview, office_code)
    
    target_folder_path = folder_path
    if not is_preview:
        subfolder = get_subfolder_from_filename(filename)
        if subfolder:
            target_folder_path = f"{folder_path}/{subfolder}"
        
    source_doc = f"{target_folder_path}/{filename}"
    encoded_source = urllib.parse.quote(source_doc, safe='/:')
    
    if not action:
        action = "edit" if is_preview else "default"
        
    return (
        f"{site_url}/_layouts/15/Doc.aspx"
        f"?sourcedoc={encoded_source}&action={action}"
    )
