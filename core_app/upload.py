import requests
import urllib.parse
import os


def upload_file_automatically(folder_url, local_file_path, target_file_name):
    # Establish a persistent session to hold cookies
    session = requests.Session()

    # ---------------------------------------------------------
    # STEP 1: Visit the folder URL to generate the Guest Cookies
    # ---------------------------------------------------------
    print("1. Fetching guest cookies...")

    # We disguise the script as a browser to avoid getting blocked
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36'
    })

    # Hitting the URL assigns the 'FedAuth' cookie to our session
    initial_response = session.get(folder_url)
    initial_response.raise_for_status()

    # ---------------------------------------------------------
    # STEP 2: Request a fresh Anti-Forgery Token (x-requestdigest)
    # ---------------------------------------------------------
    print("2. Generating fresh x-requestdigest token...")
    base_url = "https://horusuni-my.sharepoint.com"
    site_url = f"{base_url}/personal/aelshafee_horus_edu_eg"
    context_info_url = f"{site_url}/_api/contextinfo"

    # POST to contextinfo with the cookies we just got
    ctx_headers = {
        'Accept': 'application/json;odata=verbose',
        'Content-Type': 'application/json;odata=verbose'
    }

    ctx_response = session.post(context_info_url, headers=ctx_headers)

    if ctx_response.status_code != 200:
        print("Failed to get authorization token. The link might require a specific sharing token.")
        print(ctx_response.text)
        return

    request_digest = ctx_response.json()['d']['GetContextWebInformation']['FormDigestValue']

    # ---------------------------------------------------------
    # STEP 3: Upload the File
    # ---------------------------------------------------------
    print(f"3. Uploading '{target_file_name}'...")
    folder_path = "/personal/aelshafee_horus_edu_eg/Documents/ESSIC_Docs"

    encoded_folder = urllib.parse.quote(folder_path, safe='')
    encoded_filename = urllib.parse.quote(target_file_name, safe='')

    upload_endpoint = (
        f"{site_url}/_api/web/GetFolderByServerRelativePath(DecodedUrl=@a1)/Files/AddUsingPath"
        f"(DecodedUrl=@a2,AutoCheckoutOnInvalidData=@a3)"
        f"?@a1=%27{encoded_folder}%27&@a2=%27{encoded_filename}%27&@a3=true"
    )

    # Note: We don't pass cookies here because session.post handles them automatically
    upload_headers = {
        'Accept': 'application/json;odata=verbose',
        'Content-Type': 'application/octet-stream',
        'X-RequestDigest': request_digest
    }

    try:
        with open(local_file_path, 'rb') as f:
            upload_response = session.post(upload_endpoint, headers=upload_headers, data=f)

        if upload_response.status_code in [200, 201, 202]:
            print("Upload successful!")
        else:
            print(f"Upload failed: {upload_response.status_code}")
            print(upload_response.text)

    except FileNotFoundError:
        print(f"Error: Could not find the file '{local_file_path}'")


# ==========================================
# Run the script
# ==========================================
if __name__ == "__main__":
    # The URL you provided
    sharepoint_url = "https://horusuni-my.sharepoint.com/:f:/g/personal/aelshafee_horus_edu_eg/IgD0qoF1DQWTSqbxLv0Ccb5gAe65TdO255mPl-HXKm078jo"

    local_file = "README.md"
    sharepoint_name = "README.md"

    upload_file_automatically(sharepoint_url, local_file, sharepoint_name)