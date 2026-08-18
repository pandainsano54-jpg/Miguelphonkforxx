"""
AUTO TOKEN GENERATOR - Genera tokens nuevos automáticamente cada X horas
Railway Version - ENGLISH
=================================================================

Genera tokens nuevos y los añade a tokens.json
Se ejecuta en loop automático cada X horas

Usage:
    python auto_token_generator.py            -> genera una vez
    python auto_token_generator.py --loop     -> loop continuo, genera cada X horas
"""

import base64
import json
import time
import os
import argparse
from pathlib import Path
from urllib import request, error
import traceback

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------
HOST = "https://animalcompany.us-east1.nakamacloud.io"
AUTH_URL = f"{HOST}/v2/account/authenticate/steam?create=true&sync=false"
SERVER_KEY = "6URuTSlDKKfYbuDW"

# Archivo donde guardar tokens
TOKENS_FILE = Path("tokens.json")

# ← IMPORTANTE: Credenciales Steam (configura como variables de entorno)
STEAM_TICKET = os.getenv("STEAM_TICKET", "")
STEAM_ACCOUNT_ID = os.getenv("STEAM_ACCOUNT_ID", "")

# Cada cuántos MINUTOS generar token nuevo
GENERATION_INTERVAL = int(os.getenv("TOKEN_GENERATION_INTERVAL", "50"))  # 50 minutos por defecto

# Máximo de tokens a mantener (elimina los más viejos)
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "5"))

# ---------------------------------------------------------------------------
def validate_credentials():
    """Validate that Steam credentials are configured"""
    if not STEAM_TICKET:
        raise ValueError(
            "❌ Missing STEAM_TICKET\n"
            "Configure it in Railway → Variables → STEAM_TICKET"
        )
    if not STEAM_ACCOUNT_ID:
        raise ValueError(
            "❌ Missing STEAM_ACCOUNT_ID\n"
            "Configure it in Railway → Variables → STEAM_ACCOUNT_ID"
        )


def load_tokens() -> dict:
    """Load tokens from file or create empty structure"""
    try:
        if TOKENS_FILE.exists():
            content = TOKENS_FILE.read_text()
            return json.loads(content)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"[GENERATOR] ⚠️ Error loading tokens: {e}")
    
    # Return empty structure if file doesn't exist
    return {"tokens": []}


def save_tokens(tokens: dict) -> None:
    """Persist tokens to file"""
    try:
        TOKENS_FILE.write_text(json.dumps(tokens, indent=2))
        print(f"[GENERATOR] ✅ Tokens saved to {TOKENS_FILE}")
    except Exception as e:
        print(f"[GENERATOR] ❌ Error saving tokens: {e}")
        traceback.print_exc()


def generate_new_token() -> dict:
    """
    Generate a new token from Steam credentials
    Returns dict with token and refresh_token
    """
    try:
        # Create Basic Auth header
        basic = base64.b64encode(f"{SERVER_KEY}:".encode()).decode()

        # Prepare request body with Steam credentials
        body = json.dumps({
            "account": {
                "steam": {
                    "ticket": STEAM_TICKET,
                    "account_id": STEAM_ACCOUNT_ID
                }
            }
        }).encode()

        # Create request
        req = request.Request(
            AUTH_URL,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Basic {basic}",
            },
        )

        # Execute request
        print(f"[GENERATOR] 🔄 Generating new token from Steam credentials...")
        with request.urlopen(req, timeout=10) as resp:
            response_data = json.loads(resp.read())

        # Extract tokens from response
        token = response_data.get("token", "")
        refresh_token = response_data.get("refresh_token", "")

        if not token or not refresh_token:
            raise ValueError("Response missing token or refresh_token")

        print(f"[GENERATOR] ✅ New token generated successfully!")
        
        return {
            "token": token,
            "refresh_token": refresh_token,
            "created_at": int(time.time())
        }

    except error.HTTPError as e:
        error_body = e.read().decode()
        print(f"[GENERATOR] ❌ HTTP Error {e.code}: {error_body[:200]}")
        return None

    except error.URLError as e:
        print(f"[GENERATOR] ❌ Connection error: {e}")
        return None

    except Exception as e:
        print(f"[GENERATOR] ❌ Error: {e}")
        traceback.print_exc()
        return None


def add_token_to_pool(new_token_data: dict, tokens: dict) -> dict:
    """Add new token to the pool and remove oldest if MAX_TOKENS exceeded"""
    
    # Create token entry
    token_id = f"token_{len(tokens['tokens']) + 1}"
    token_entry = {
        "id": token_id,
        "token": new_token_data["token"],
        "refresh_token": new_token_data["refresh_token"],
        "created_at": new_token_data.get("created_at", int(time.time()))
    }
    
    # Add new token
    tokens["tokens"].append(token_entry)
    print(f"[GENERATOR] ✅ Token added to pool as '{token_id}'")
    
    # Remove oldest tokens if exceeded max
    if len(tokens["tokens"]) > MAX_TOKENS:
        # Sort by created_at and remove oldest
        tokens["tokens"].sort(key=lambda x: x.get("created_at", 0))
        removed_count = len(tokens["tokens"]) - MAX_TOKENS
        tokens["tokens"] = tokens["tokens"][removed_count:]
        print(f"[GENERATOR] 🗑️ Removed {removed_count} oldest token(s). Pool: {len(tokens['tokens'])}/{MAX_TOKENS}")
    
    return tokens


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true", help="Run in loop, generating tokens periodically")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("🎟️  AUTO TOKEN GENERATOR - ANIMAL COMPANY")
    print("=" * 60)
    
    try:
        validate_credentials()
    except ValueError as e:
        print(f"[GENERATOR] ❌ {e}")
        return

    if not args.loop:
        print("[GENERATOR] Single execution mode...")
        try:
            new_token = generate_new_token()
            if new_token:
                tokens = load_tokens()
                tokens = add_token_to_pool(new_token, tokens)
                save_tokens(tokens)
                print(f"[GENERATOR] ✅ Total tokens in pool: {len(tokens['tokens'])}/{MAX_TOKENS}")
            else:
                print("[GENERATOR] ❌ Failed to generate token")
        except Exception as e:
            print(f"[GENERATOR] ❌ Error: {e}")
        return

    # Loop mode
    print(f"[GENERATOR] 🔁 Loop mode ACTIVE (every {GENERATION_INTERVAL} minutes)")
    print(f"[GENERATOR] 📊 Max tokens in pool: {MAX_TOKENS}\n")
    
    failed_attempts = 0
    MAX_ATTEMPTS = 3

    while True:
        try:
            # Generate new token
            new_token = generate_new_token()
            
            if new_token:
                # Load current tokens
                tokens = load_tokens()
                
                # Add new token and manage pool
                tokens = add_token_to_pool(new_token, tokens)
                
                # Save updated tokens
                save_tokens(tokens)
                print(f"[GENERATOR] 📊 Pool status: {len(tokens['tokens'])}/{MAX_TOKENS} tokens\n")
                
                failed_attempts = 0
            else:
                failed_attempts += 1
                print(f"[GENERATOR] ⚠️ Failed to generate token (attempt {failed_attempts}/{MAX_ATTEMPTS})\n")
                
                if failed_attempts >= MAX_ATTEMPTS:
                    print(f"[GENERATOR] ❌ Too many failed attempts. Stopping.")
                    break
            
            # Wait before next generation
            wait_time = GENERATION_INTERVAL * 60  # Convert minutes to seconds
            print(f"[GENERATOR] ⏱️  Next token generation in {GENERATION_INTERVAL} minutes...")
            print(f"[GENERATOR] ⏱️  Sleeping for {wait_time}s...\n")
            time.sleep(wait_time)

        except KeyboardInterrupt:
            print("\n[GENERATOR] ⛔ User interrupted")
            break

        except Exception as e:
            failed_attempts += 1
            print(f"[GENERATOR] ⚠️ Failed attempt {failed_attempts}/{MAX_ATTEMPTS}: {e}\n")
            
            if failed_attempts >= MAX_ATTEMPTS:
                print(f"[GENERATOR] ❌ Too many failed attempts. Stopping.")
                break
            
            # Wait before retry
            wait_time = 300  # 5 minutes retry interval
            print(f"[GENERATOR] ⏱️  Retrying in {wait_time}s...\n")
            time.sleep(wait_time)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[GENERATOR] ❌ Fatal error: {e}\n")
        traceback.print_exc()
