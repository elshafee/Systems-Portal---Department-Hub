import os
import requests
import urllib.parse
from flask import Flask
from services.onedrive import get_sharepoint_config, LAST_ERROR

def delete_file_from_share(target_file_name: str) -> bool:
    share_url, base_url, site_url, folder_path = get_sharepoint_config()
    
    if not share_url:
        return False
        
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0'
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

        file_path = f"{folder_path}/{target_file_name}"
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
            print("Successfully deleted!")
            return True
        else:
            print("Failed to delete:", delete_response.status_code, delete_response.text)
            return False
    except Exception as e:
        print("Exception:", e)
        return False

# test it
delete_file_from_share("NonExistentFile123.docx")
