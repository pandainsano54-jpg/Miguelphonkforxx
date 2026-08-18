"""
Auto Token Refresher - MEJORADO
Railway Version - ENGLISH
=================================================================

Refresca TODOS los tokens cada 60 segundos (en lugar de 120).
Soporta múltiples tokens en tokens.json

Usage:
    python refresh_token.py            -> refresh una vez
    python refresh_token.py --loop     -> loop continuo, refresh cada 60 segundos
"""

import base64
import json
import time
import argparse
import threading
from pathlib import Path
from urllib import request, error
import traceback

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------
HOST = "https://animalcompany.us-east1.nakamacloud.io"
REFRESH_URL = f"{HOST}/v2/account/session/refresh"
SERVER_KEY = "6URuTSlDKKfYbuDW"

# File to store tokens
TOKENS_FILE = Path("tokens.json")

# ← MEJORADO: Refresh cada 60 segundos (en lugar de 120)
REFRESH_INTERVAL = 60  # 1 minuto

# ---------------------------------------------------------------------------
def load_tokens() -> dict:
    """Load tokens from file"""
    try:
        if TOKENS_FILE.exists():
            content = TOKENS_FILE.read_text()
            tokens = json.loads(content)
            print(f"[REFRESH] ✅ Tokens loaded from {TOKENS_FILE}")
            return tokens
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"[REFRESH] ❌ Error loading tokens: {e}")
        raise


def save_tokens(tokens: dict) -> None:
    """Persist tokens to file"""
    try:
        TOKENS_FILE.write_text(json.dumps(tokens, indent=2))
        print(f"[REFRESH] ✅ Tokens saved to {TOKENS_FILE}")
    except Exception as e:
        print(f"[REFRESH] ❌ Error saving tokens: {e}")
        traceback.print_exc()


def decode_jwt_exp(jwt_token: str) -> int:
    """Decode JWT 'exp' field without verifying signature"""
    try:
        payload_b64 = jwt_token.split(".")[1]
        padding = "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + padding))
        return payload.get("exp", 0)
    except Exception as e:
        print(f"[REFRESH] ⚠️ Error decoding JWT: {e}")
        return 0


def refresh_single_token(token_data: dict, token_index: int) -> dict:
    """
    Refresh a single token and return updated data.
    Returns None if refresh fails.
    """
    token_id = token_data.get("id", f"token_{token_index}")
    
    try:
        # Create Basic Auth header
        basic = base64.b64encode(f"{SERVER_KEY}:".encode()).decode()

        # Prepare request body
        body = json.dumps({"token": token_data["refresh_token"]}).encode()

        # Create request
        req = request.Request(
            REFRESH_URL,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Basic {basic}",
            },
        )

        # Execute request
        with request.urlopen(req, timeout=10) as resp:
            response_data = json.loads(resp.read())

        # Update tokens
        updated_data = dict(token_data)
        updated_data["token"] = response_data.get("token", token_data["token"])
        updated_data["refresh_token"] = response_data.get("refresh_token", token_data["refresh_token"])
        
        exp = decode_jwt_exp(updated_data["token"])
        exp_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(exp))
        
        print(f"[REFRESH] ✅ {token_id} refreshed | Expires: {exp_time}")
        
        return updated_data

    except error.HTTPError as e:
        error_body = e.read().decode()
        print(f"[REFRESH] ❌ {token_id} HTTP Error {e.code}: {error_body[:100]}")
        return None

    except error.URLError as e:
        print(f"[REFRESH] ❌ {token_id} Connection error: {e}")
        return None

    except Exception as e:
        print(f"[REFRESH] ❌ {token_id} Error: {e}")
        return None


def refresh_all_tokens(tokens_data: dict) -> dict:
    """Refresh all tokens in parallel using threads"""
    print(f"\n[REFRESH] 🔄 Refrescando {len(tokens_data['tokens'])} tokens en paralelo...")
    
    results = {}
    threads = []
    
    def refresh_worker(idx, token_data):
        updated = refresh_single_token(token_data, idx + 1)
        results[idx] = updated
    
    # Create threads for each token
    for idx, token_data in enumerate(tokens_data["tokens"]):
        thread = threading.Thread(target=refresh_worker, args=(idx, token_data))
        threads.append(thread)
        thread.start()
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()
    
    # Update tokens with results
    updated_tokens = list(tokens_data["tokens"])
    successful = 0
    
    for idx, updated_data in results.items():
        if updated_data is not None:
            updated_tokens[idx] = updated_data
            successful += 1
        else:
            print(f"[REFRESH] ⚠️ Token {idx + 1} refresh failed, keeping previous version")
    
    tokens_data["tokens"] = updated_tokens
    
    print(f"[REFRESH] ✅ Refrescados {successful}/{len(tokens_data['tokens'])} tokens exitosamente\n")
    
    return tokens_data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true", help="Run in loop, refreshing every 60 seconds")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("🔄 AUTO TOKEN REFRESHER - MÚLTIPLES TOKENS (ANIMAL COMPANY)")
    print("=" * 60)
    
    try:
        tokens_data = load_tokens()
    except Exception as e:
        print(f"[REFRESH] ❌ Fatal error loading tokens: {e}")
        return

    if not args.loop:
        print("[REFRESH] Single execution mode...")
        try:
            updated = refresh_all_tokens(tokens_data)
            save_tokens(updated)
        except Exception as e:
            print(f"[REFRESH] ❌ Single refresh failed: {e}")
        return

    # Loop mode
    print(f"[REFRESH] 🔁 Loop mode ACTIVE (every {REFRESH_INTERVAL}s = every minuto)\n")
    
    failed_attempts = 0
    MAX_ATTEMPTS = 5

    while True:
        try:
            # Check expiration of first token as reference
            first_token = tokens_data["tokens"][0].get("token", "")
            exp = decode_jwt_exp(first_token)
            now = int(time.time())
            seconds_remaining = exp - now

            if seconds_remaining < 0:
                print(f"[REFRESH] ⚠️ ¡Tokens ya expirados! Refrescando inmediatamente...")
                tokens_data = refresh_all_tokens(tokens_data)
                save_tokens(tokens_data)
                failed_attempts = 0
            else:
                # Wait before next refresh
                print(f"[REFRESH] ⏱️ Próximo refresh en {REFRESH_INTERVAL}s ({seconds_remaining}s hasta vencimiento)")
                time.sleep(REFRESH_INTERVAL)
                
                tokens_data = refresh_all_tokens(tokens_data)
                save_tokens(tokens_data)
                failed_attempts = 0

        except KeyboardInterrupt:
            print("\n[REFRESH] ⛔ User interrupted")
            break

        except Exception as e:
            failed_attempts += 1
            print(f"[REFRESH] ⚠️ Failed attempt {failed_attempts}/{MAX_ATTEMPTS}: {e}")
            
            if failed_attempts >= MAX_ATTEMPTS:
                print(f"[REFRESH] ❌ Too many failed attempts. Aborting.")
                break
            
            # Wait before retry
            wait_time = 30 * failed_attempts  # 30s, 60s, 90s, etc.
            print(f"[REFRESH] ⏱️ Retrying in {wait_time}s...")
            time.sleep(wait_time)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[REFRESH] ❌ Fatal error: {e}\n")
        traceback.print_exc()
