import requests
import urllib.parse
import os

def download_file_automatically(original_sharing_link, target_file_name, local_save_path):
    """
    Downloads a file from a SharePoint folder using an anonymous guest sharing link.
    """
    session = requests.Session()
    
    # Disguise the script as a browser
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5'
    })
    
    # ---------------------------------------------------------
    # STEP 1: Visit the original sharing link to get cookies
    # ---------------------------------------------------------
    print("1. Following sharing link to acquire Guest Cookies...")
    response = session.get(original_sharing_link)
    
    if 'FedAuth' not in session.cookies:
        print("❌ Error: The FedAuth cookie was not set. Check your sharing link.")
        return

    print("   ✓ Guest cookies acquired successfully!")

    # ---------------------------------------------------------
    # STEP 2: Download the File
    # ---------------------------------------------------------
    print(f"2. Downloading '{target_file_name}'...")
    
    base_url = "https://horusuni-my.sharepoint.com"
    site_url = f"{base_url}/personal/aelshafee_horus_edu_eg"
    
    # Construct the full server-relative path to the file
    folder_path = "/personal/aelshafee_horus_edu_eg/Documents/ESSIC_Docs"
    file_path = f"{folder_path}/{target_file_name}"
    
    # SharePoint API requires URL-encoded paths
    encoded_file_path = urllib.parse.quote(file_path, safe='')
    
    # The /$value endpoint returns the raw binary content of the file
    download_endpoint = (
        f"{site_url}/_api/web/GetFileByServerRelativePath(DecodedUrl=@v)/$value"
        f"?@v=%27{encoded_file_path}%27"
    )

    # Stream=True allows us to download large files without overloading RAM
    download_response = session.get(download_endpoint, stream=True)

    if download_response.status_code == 200:
        # Write the file to disk in 8KB chunks
        with open(local_save_path, 'wb') as f:
            for chunk in download_response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"   ✓ Download successful! Saved to: {local_save_path}")
    else:
        print(f"❌ Download failed with status code {download_response.status_code}.")
        print("Response:", download_response.text)


# ==========================================
# Run the script
# ==========================================
if __name__ == "__main__":
    
    # MUST BE THE ORIGINAL SHARING LINK
    sharepoint_url = "https://horusuni-my.sharepoint.com/:f:/g/personal/aelshafee_horus_edu_eg/IgD0qoF1DQWTSqbxLv0Ccb5gAe65TdO255mPl-HXKm078jo"
    
    # The name of the file exactly as it appears in SharePoint
    file_to_download = "README.md" 
    
    # What you want to name the file on your local machine
    save_as = "Downloaded_README.md" 
    
    download_file_automatically(sharepoint_url, file_to_download, save_as)