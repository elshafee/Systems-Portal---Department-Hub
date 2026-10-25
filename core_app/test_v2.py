#!/usr/bin/env python3
"""
DeepSeek chat client – PoW token built exactly like the official SDK.
"""

import json
import base64
import hashlib
import hmac      # <‑‑ needed for the HMAC signature
import requests

# --------------------------------------------------------------------------- #
# USER‑CONFIGURABLE VALUES                                                   #
# --------------------------------------------------------------------------- #

AUTH_TOKEN = "UdEr89d7THoEVG0/XGOSDxZ5fY3emBQ4WGMYmFTvxN961jPpZaBaGAB2HNw38LHj"

# Cookies that the official client sends (kept as a single string)
COOKIE_STR = (
    "aws-waf-token=93f02ce3-4c48-43e0-9291-b3940ec5c8ca:CQoAqoUsen4RAAAA:A8pADboqSAlcNp+TNLqXDC7QaclVPUYKGggmAo1g0Of+f1KHpFUXYQYG6nyTKN6mUgX7uZ14sWSNfFSJdQhkwcDNmVNWHCFyMYL8XsFWrjie7ECoQCae4CcjC7I9wblkxo+O29jj0VtfLVfgV+4dcfgaZhLWw44vnj9kWW0H0FUHxRxdjazHcJDYhGz2B2ABzWlAFA==; "
    "smidV2=20260707092836ff5e09b80c7367384ddb578e25b12009e0858e90382af0; "
    ".thumbcache_6b2e5483f9d858d7c661c5e276b6a6ae=GI/K69fEayLWUX0kj9taTv2zxARcNyZwXbGvrldZNkNsVioTt01bdEYlXt2niFq0IZ+im2hMf3Wwl6IxD6Uhkg%3D%3D; "
    "ds_session_id=83b36bf402b24d46ba432c261c9d9181"
)

# --------------------------------------------------------------------------- #
# HELPERS                                                                    #
# --------------------------------------------------------------------------- #

def base64url_encode(data: bytes) -> str:
    """Base‑64URL encode without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

def sha3_256(d: bytes) -> bytes:
    """SHA‑3‑256 hash."""
    return hashlib.sha3_256(d).digest()

def solve_pow(challenge_hex: str, salt_hex: str, difficulty: int) -> tuple[int, str]:
    """
    Find a nonce such that SHA3‑256(challenge + salt + nonce) < target.
    Returns (nonce, hash_hex).
    """
    challenge = bytes.fromhex(challenge_hex)
    salt = bytes.fromhex(salt_hex)

    target = (1 << 256) // difficulty   # server’s difficulty formula

    for nonce in range(0, 2**32):
        h = sha3_256(challenge + salt + str(nonce).encode())
        if int.from_bytes(h, "big") < target:
            return nonce, h.hex()
    raise RuntimeError("PoW not found")

def create_pow_response(challenge: dict, answer: int) -> str:
    """
    Build the token that must be sent in `x-ds-pow-response`.

    The JSON structure is:

        {
            "alg"       : "DeepSeekHashW1",
            "challenge" : challenge["challenge"],
            "salt"      : challenge["salt"],
            "answer"    : answer,
            "signature" : HMAC‑SHA256(key=challenge["signature"],
                                      msg=challenge_bytes + salt_bytes + answer_ascii),
            "target_path": challenge["target_path"]
        }

    The whole object is Base‑64URL encoded without padding.
    """
    challenge_bytes = bytes.fromhex(challenge["challenge"])
    salt_bytes      = bytes.fromhex(challenge["salt"])

    # HMAC‑SHA256 with the challenge’s own signature as key
    key = bytes.fromhex(challenge["signature"])
    signature = hmac.new(
        key,
        challenge_bytes + salt_bytes + str(answer).encode(),
        hashlib.sha256
    ).hexdigest()

    token_dict = {
        "alg": "DeepSeekHashW1",                 # the SDK always uses this
        "challenge": challenge["challenge"],
        "salt": challenge["salt"],
        "answer": answer,
        "signature": signature,
        "target_path": challenge["target_path"],
    }

    return base64url_encode(json.dumps(token_dict, separators=(",", ":")).encode())

# --------------------------------------------------------------------------- #
# MAIN                                                                       #
# --------------------------------------------------------------------------- #

def main():
    session = requests.Session()

    # ---- common headers ----------------------------------------------------
    base_headers = {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "authorization": f"Bearer {AUTH_TOKEN}",
        "content-type": "application/json",
        "dnt": "1",
        "origin": "https://chat.deepseek.com",
        "priority": "u=1, i",
        "referer": "https://chat.deepseek.com/",
        "sec-ch-ua": '"Google Chrome";v="149", "Chromium";v="149", "Not)A;Brand";v="24"',
        "sec-ch-ua-mobile": "?1",
        "sec-ch-ua-platform": "\"Android\"",
        "sec_fetch_dest": "empty",
        "sec_fetch_mode": "cors",
        "sec_fetch_site": "same-origin",
        "user-agent": (
            "Mozilla/5.0 (Linux; Android 15; Pixel 9) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/149.0.0.0 Mobile Safari/537.36"
        ),
        "x-client-bundle-id": "com.deepseek.chat",
        "x-client_locale": "en_US",
        "x-client_platform": "web",
        "x-client_timezone_offset": "10800",
        "x-client_version": "2.2.0",
        "Cookie": COOKIE_STR,
    }

    # ---- 1️⃣ Get PoW challenge --------------------------------------------
    print("Requesting PoW challenge…")
    pow_url = "https://chat.deepseek.com/api/v0/chat/create_pow_challenge"
    resp = session.post(pow_url, headers=base_headers,
                        json={"target_path": "/api/v0/chat/completion"})
    resp.raise_for_status()
    challenge = resp.json()["data"]["biz_data"]["challenge"]
    print("Challenge received:", challenge)

    # ---- 2️⃣ Solve PoW -------------------------------------------------------
    print(f"Solving PoW (difficulty={challenge['difficulty']})…")
    nonce, _ = solve_pow(challenge["challenge"],
                         challenge["salt"],
                         challenge["difficulty"])
    print("Solved – nonce:", nonce)

    # ---- 3️⃣ Create session ---------------------------------------------------
    print("Creating chat session…")
    sess_url = "https://chat.deepseek.com/api/v0/chat_session/create"
    resp = session.post(sess_url, headers=base_headers)
    resp.raise_for_status()
    sess_id = resp.json()["data"]["biz_data"]["id"]
    print("Session created:", sess_id)

    # ---- 4️⃣ Build PoW response header ---------------------------------------
    pow_token = create_pow_response(challenge, nonce)

    # ---- 5️⃣ Send prompt -------------------------------------------------------
    print("Sending prompt…")
    comp_url = "https://chat.deepseek.com/api/v0/chat/completion"
    headers = base_headers.copy()
    headers["x-ds-pow-response"] = pow_token

    prompt_payload = {
        "chat_session_id": sess_id,
        "parent_message_id": None,
        "model_type": "default",
        "prompt": "Hello! Can you confirm you are receiving this message?",
        "ref_file_ids": [],
        "thinking_enabled": False,
        "search_enabled": True,
        "action": None,
        "preempt": False,
    }

    resp = session.post(comp_url, headers=headers,
                        json=prompt_payload, stream=True)
    print("Response status:", resp.status_code)

    # ---- 6️⃣ Stream result -----------------------------------------------------
    for line in resp.iter_lines():
        if line:
            decoded = line.decode().lstrip("data: ")
            if decoded:
                print(decoded)

if __name__ == "__main__":
    main()
