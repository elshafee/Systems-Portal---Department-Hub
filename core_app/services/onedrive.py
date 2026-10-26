"""
services/onedrive.py

Handles OneDrive/SharePoint interactions using Guest Cookies via requests.
"""
import os
import requests
import urllib.parse
import re

LAST_ERROR = ""

def get_sharepoint_config(is_preview: bool = False):
    share_url = os.environ.get("ONEDRIVE_SHARE_URL", "").strip('"\'')
    if is_preview:
        share_url = os.environ.get("ONEDRIVE_PREVIEW_SHARE_URL", share_url).strip('"\'')
        
    if not share_url:
        share_url = None
        
    base_url = "https://horusuni-my.sharepoint.com"
    site_url = f"{base_url}/personal/aelshafee_horus_edu_eg"
    
    if is_preview:
        folder_path = "/personal/aelshafee_horus_edu_eg/Documents/previews"
    else:
        folder_path = os.environ.get("SYSTEM_ONEDRIVE_FOLDER", "/personal/aelshafee_horus_edu_eg/Documents/ESSIC_Docs")
        
    return share_url, base_url, site_url, folder_path

def get_subfolder_from_filename(filename: str) -> str:
    if not filename:
        return None
    match = re.search(r'(\d{2}-\d{4})\.(docx|pdf)$', filename, re.IGNORECASE)
    if match:
        return match.group(1)
    return None

def upload_file_to_share(local_filepath: str, dest_filename: str, is_preview: bool = False) -> bool:
    """
    Uploads a local file to the shared OneDrive folder using Guest Cookies.
    Returns True on success, False on failure.
    """
    global LAST_ERROR
    LAST_ERROR = ""
    share_url, base_url, site_url, folder_path = get_sharepoint_config(is_preview)
    
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

        target_folder_path = folder_path
        subfolder = get_subfolder_from_filename(dest_filename)
        if subfolder:
            encoded_parent = urllib.parse.quote(folder_path, safe='')
            create_folder_url = f"{site_url}/_api/web/GetFolderByServerRelativePath(DecodedUrl=@v)/Folders/add('{subfolder}')?@v=%27{encoded_parent}%27"
            create_headers = {
                'Accept': 'application/json;odata=verbose',
                'Content-Type': 'application/json;odata=verbose',
                'X-RequestDigest': request_digest
            }
            # Ignore response - if it exists, it's fine
            session.post(create_folder_url, headers=create_headers)
            target_folder_path = f"{folder_path}/{subfolder}"

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


def delete_file_from_share(target_file_name: str, is_preview: bool = False) -> bool:
    """
    Deletes a file from the shared OneDrive folder using Guest Cookies.
    """
    share_url, base_url, site_url, folder_path = get_sharepoint_config(is_preview)
    
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

        target_folder_path = folder_path
        subfolder = get_subfolder_from_filename(target_file_name)
        if subfolder:
            target_folder_path = f"{folder_path}/{subfolder}"

        file_path = f"{target_folder_path}/{target_file_name}"
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
            return True
        elif is_preview:
            # Guest cookies may lack DELETE permissions on SharePoint.
            # Truncate/clear the file so no stale data remains in previews.
            encoded_folder = urllib.parse.quote(target_folder_path, safe='')
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
            return clear_resp.status_code in [200, 201, 202]
        return False
    except Exception as e:
        print(f"[Delete Exception] {e}")
        return False


def download_file_from_share(target_file_name: str, local_save_path: str, is_preview: bool = False) -> bool:
    """
    Downloads a file from SharePoint folder using Guest Cookies.
    """
    share_url, base_url, site_url, folder_path = get_sharepoint_config(is_preview)
    
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
        # STEP 1: Acquire Guest Cookies
        response = session.get(share_url)
        if 'FedAuth' not in session.cookies:
            print("[Download Error] The FedAuth cookie was not set. Check your sharing link.")
            return False

        # STEP 2: Download the File
        target_folder_path = folder_path
        subfolder = get_subfolder_from_filename(target_file_name)
        if subfolder:
            target_folder_path = f"{folder_path}/{subfolder}"
            
        file_path = f"{target_folder_path}/{target_file_name}"
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
        else:
            print(f"[Download Error] {download_response.status_code}")
            print(download_response.text)
            return False
            
    except Exception as e:
        print(f"[Download Exception] {e}")
        return False


# app.py calls upload_file_to_onedrive(...), but this module only defined
# upload_file_to_share(...) — that mismatch would raise an ImportError the
# first time a document gets auto-approved. Alias it so the existing call
# site in app.py keeps working without changes.
upload_file_to_onedrive = upload_file_to_share


def get_word_online_url(filename: str, is_preview: bool = False) -> str:
    """
    Returns the direct Word Online (SharePoint viewer) URL for a given filename.
    The URL opens the file in the browser without redirecting through Flask.
    """
    _, _, _, folder_path = get_sharepoint_config(is_preview)
    base_url = "https://horusuni-my.sharepoint.com"
    site_url = f"{base_url}/personal/aelshafee_horus_edu_eg"
    
    target_folder_path = folder_path
    subfolder = get_subfolder_from_filename(filename)
    if subfolder:
        target_folder_path = f"{folder_path}/{subfolder}"
        
    encoded_filename = urllib.parse.quote(filename, safe='')
    # Word Online direct link: /_layouts/15/Doc.aspx?sourcedoc=<server_relative_path>&action=default
    source_doc = f"{target_folder_path}/{filename}"
    encoded_source = urllib.parse.quote(source_doc, safe='/:')
    return (
        f"{site_url}/_layouts/15/Doc.aspx"
        f"?sourcedoc={encoded_source}&action=default"
    )