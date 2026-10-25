#!/usr/bin/env python3
"""
DeepSeek chat client – updated to use the new PoW JSON payload.
"""

import json
import base64
import hashlib
import time
from urllib.parse import urljoin

import requests
import jwt  # pip install pyjwt


# --------------------------------------------------------------------------- #
# USER‑CONFIGURABLE VALUES -------------------------------------------------- #
AUTH_TOKEN = "UdEr89d7THoEVG0/XGOSDxZ5fY3emBQ4WGMYmFTvxN961jPpZaBaGAB2HNw38LHj"

# Exact cookie string that the browser sends (copy‑paste from DevTools)
COOKIE_STR = (
    "aws-waf-token=93f02ce3-4c48-43e0-9291-b3940ec5c8ca:CQoAqoUsen4RAAAA:A8pADboqSAlcNp+TNLqXDC7QaclVPUYKGggmAo1g0Of+f1KHpFUXYQYG6nyTKN6mUgX7uZ14sWSNfFSJdQhkwcDNmVNWHCFyMYL8XsFWrjie7ECoQCae4CcjC7I9wblkxo+O29jj0VtfLVfgV+4dcfgaZhLWw44vnj9kWW0H0FUHxRxdjazHcJDYhGz2B2ABzWlAFA==; "
    "smidV2=20260707092836ff5e09b80c7367384ddb578e25b93c82009e0858e90382af0; "
    ".thumbcache_6b2e5483f9d858d7c661c5e276b6a6ae=GI/K69fEayLWUX0kj9taTv2zxARcNyZwXbGvrldZNkNsVioTt01bdEYlXt2niFq0IZ+im2hMf3Wwl6IxD6Uhkg==; "
    "ds_session_id=83b36bf402b24d46ba432c261c9d9181"
)

# headers = {
#     "accept": "*/*",
#     "accept-encoding": "gzip, deflate, br, zstd",
#     "accept-language": "en-US,en;q=0.9",
#     "authorization": f"Bearer {AUTH_TOKEN}",
#     "content-type": "application/json",
#     "cookie": COOKIE_STR,
#     "dnt": "1",
#     "origin": "https://chat.deepseek.com",
#     "priority": "u=1, i",
#     "referer": "https://chat.deepseek.com/a/chat/s/f09ac7d7-515a-4439-8f36-87ff2b0bb1ac",
#     "sec-ch-ua": "\"Google Chrome\";v=\"149\", \"Chromium\";v=\"149\", \"Not)A;Brand\";v=\"24\"",
#     "sec-ch-ua-mobile": "?1",
#     "sec-ch-ua-platform": "\"Android\"",
#     "sec-fetch-dest": "empty",
#     "sec-fetch-mode": "cors",
#     "sec-fetch-site": "same-origin",
#     "user-agent": ("Mozilla/5.0 (Linux; Android 15; Pixel 9) "
#                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36"),
#     "x-client-bundle-id": "com.deepseek.chat",
#     "x-client-locale": "en_US",
#     "x-client-platform": "web",
#     "x-client-timezone-offset": "10800",
#     "x-client-version": "2.2.0",
#     "x-ds-pow-response": pow_jwt,   # the JWT you constructed
# }

# --------------------------------------------------------------------------- #
# HELPER FUNCTIONS -------------------------------------------------------- #

def base64url_decode(data: str) -> bytes:
    data += "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data)


def parse_jwt(token: str) -> dict:
    _, payload_b64, _ = token.split(".")
    return json.loads(base64url_decode(payload_b64))


def encode_jwt_unsigned(payload: dict) -> str:
    """Create an unsigned JWT (alg='none')."""
    header = {"typ": "JWT", "alg": "none"}
    hdr_b64 = base64.urlsafe_b64encode(json.dumps(header, separators=(",", ":")).encode()).rstrip(b"=").decode()
    plb_b64 = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).rstrip(b"=").decode()
    return f"{hdr_b64}.{plb_b64}."


def sha3_256(data: bytes) -> bytes:
    return hashlib.sha3_256(data).digest()


def solve_pow(challenge_hex: str, salt_hex: str, difficulty: int) -> tuple[int, str]:
    """
    Brute‑force PoW for DeepSeekHashV1.

    * challenge_hex : 64‑char hex string (32 bytes)
    * salt_hex      : hex string (10 bytes in the sample)
    * difficulty    : integer from JSON

    Returns:
        nonce (int)  – the decimal number that satisfies the target
        signature (hex string) – SHA3‑256(challenge+salt+nonce_bytes)
    """
    challenge = bytes.fromhex(challenge_hex)
    salt = bytes.fromhex(salt_hex)

    # target = 2^256 // difficulty
    target = (1 << 256) // difficulty

    # Try ASCII decimal encoding first – that matches the `answer` field
    for nonce in range(0, 2**32):      # 4‑byte space is enough for all samples
        nonce_bytes = str(nonce).encode()   # e.g. b"331415"
        h = sha3_256(challenge + salt + nonce_bytes)
        if int.from_bytes(h, "big") < target:
            return nonce, h.hex()

    raise RuntimeError("PoW failed – exceeded search space")


# --------------------------------------------------------------------------- #
# MAIN -------------------------------------------------------------

def main():
    session = requests.Session()
    # Cookie header (exactly as the browser sends it)
    base_headers = {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "authorization": f"Bearer {AUTH_TOKEN}",
        "content-type": "application/json",
        "dnt": "1",
        "origin": "https://chat.deepseek.com",
        "priority": "u=1, i",
        "referer": "https://chat.deepseek.com/a/chat/s/f09ac7d7-515a-4439-8f36-87ff2b0bb1ac",
        "sec-ch-ua": "\"Google Chrome\";v=\"149\", \"Chromium\";v=\"149\", \"Not)A;Brand\";v=\"24\"",
        "sec-ch-ua-mobile": "?1",
        "sec-ch-ua-platform": "\"Android\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": (
            "Mozilla/5.0 (Linux; Android 15; Pixel 9) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36"
        ),
        "x-client-bundle-id": "com.deepseek.chat",
        "x-client-locale": "en_US",
        "x-client-platform": "web",
        "x-client-timezone-offset": "10800",
        "x-client-version": "2.2.0",
        "Cookie": COOKIE_STR,
    }

    # --------------------------------------------------------------------- #
    # 1️⃣  Get PoW challenge (now in JSON body)
    url_pow = urljoin("https://chat.deepseek.com", "/api/v0/chat/create_pow_challenge")
    print("\n=== Requesting PoW challenge ===")
    resp = session.post(url_pow, headers=base_headers, json={"target_path": "/api/v0/chat/completion"})
    print(f"Status: {resp.status_code}")
    if resp.status_code != 200:
        print("❌ Failed to get challenge – aborting")
        print(resp.text)
        return

    body = resp.json()
    try:
        challenge_obj = body["data"]["biz_data"]["challenge"]
    except KeyError:
        print("❌ Unexpected response format")
        print(json.dumps(body, indent=2))
        return

    print("\nChallenge received:")
    for k, v in challenge_obj.items():
        print(f"  {k}: {v}")

    # --------------------------------------------------------------------- #
    # 2️⃣  Solve PoW
    difficulty = challenge_obj["difficulty"]
    print(f"\nSolving PoW (difficulty={difficulty}) …")
    start = time.time()
    nonce, signature = solve_pow(
        challenge_obj["challenge"],
        challenge_obj["salt"],
        difficulty,
    )
    elapsed = time.time() - start
    print(f"✅ PoW solved in {elapsed:.2f}s – nonce={nonce}")

    # Build the payload that will be sent back
    pow_payload = {
        "algorithm": challenge_obj["algorithm"],
        "challenge": challenge_obj["challenge"],
        "salt": challenge_obj["salt"],
        "signature": signature,
        "answer": nonce,
        "difficulty": difficulty,
        "expire_at": challenge_obj["expire_at"],
        "expire_after": challenge_obj["expire_after"],
        "target_path": challenge_obj["target_path"],
    }

    # *** NEW:  base64url‑encode only the payload ***
    pow_jwt = (
        base64.urlsafe_b64encode(
            json.dumps(pow_payload, separators=(",", ":")).encode()
        )
        .rstrip(b"=")
        .decode()
    )

    # --------------------------------------------------------------------- #
    # 3️⃣  Create a new chat session
    url_session = urljoin("https://chat.deepseek.com", "/api/v0/chat_session/create")
    print("\n=== Creating chat session ===")
    resp = session.post(url_session, headers=base_headers)
    print(f"Status: {resp.status_code}")
    session_data = resp.json()
    print(f"\nChat session data: {session_data['data']['biz_data']['chat_session']['id']}")
    chat_session_id = session_data['data']['biz_data']['chat_session']['id']
    print("New session id:", chat_session_id)

    # --------------------------------------------------------------------- #
    # 4️⃣  Send prompt & stream answer
    url_completion = urljoin("https://chat.deepseek.com", "/api/v0/chat/completion")
    completion_headers = base_headers.copy()
    completion_headers["x-ds-pow-response"] = pow_jwt
    print(f"headers {completion_headers}")

    prompt_payload = {
        "chat_session_id": chat_session_id,
        "parent_message_id": None,
        "model_type": "default",
        "prompt": "hello",          # <-- change this to whatever you want
        "ref_file_ids": [],
        "thinking_enabled": False,
        "search_enabled": True,
        "action": None,
        "preempt": False,
    }

    print("\n=== Sending prompt ===")
    resp = session.post(
        url_completion,
        headers=completion_headers,
        json=prompt_payload,
        stream=True,
    )
    print(f"Status: {resp.status_code}")
    print(resp.text)

    # Consume SSE
    for line in resp.iter_lines(decode_unicode=True):
        if not line:
            continue  # keep‑alive
        if line.startswith("data:"):
            data = json.loads(line[5:].strip())
            content = data.get("content", "")
            print(content, end="", flush=True)

    print("\n--- Done ---")


if __name__ == "__main__":
    main()
# Electronic Services & Scientific Inovation Center