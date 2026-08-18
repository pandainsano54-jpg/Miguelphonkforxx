"""
Discord Token Bot - VERSIÓN SIMPLIFICADA
==============================================================

Características:
- ✅ Recarga DINÁMICA de tokens cada vez que se usa /token
- ✅ 1 solo token para todos los usuarios
- ✅ Soporta múltiples servidores Discord
- ✅ 20-minutos cooldown por usuario
- ✅ Comandos admin para resetear cooldowns
- ✅ Refresco automático cada 60 segundos
"""

import json
import os
import time
import random
from pathlib import Path
from typing import Tuple
import discord
from discord import app_commands
import traceback

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ALLOWED_GUILD_IDS_STR = os.getenv("ALLOWED_GUILD_IDS", "")
ALLOWED_USERS_STR = os.getenv("ALLOWED_USERS", "")

if not BOT_TOKEN:
    raise ValueError(
        "❌ Missing DISCORD_BOT_TOKEN\n"
        "Configure it in Railway → Variables → DISCORD_BOT_TOKEN"
    )

if not ALLOWED_GUILD_IDS_STR:
    raise ValueError(
        "❌ Missing ALLOWED_GUILD_IDS\n"
        "Configure it in Railway → Variables → ALLOWED_GUILD_IDS\n"
        "Format: ID1,ID2,ID3 (separated by commas)"
    )

# Convert to list of integers
try:
    ALLOWED_GUILD_IDS = [int(gid.strip()) for gid in ALLOWED_GUILD_IDS_STR.split(",") if gid.strip()]
except ValueError as e:
    raise ValueError(
        f"❌ ALLOWED_GUILD_IDS invalid.\n"
        f"Use format: ID1,ID2,ID3\n"
        f"Example: 123456789,987654321,555666777\n"
        f"Error: {e}"
    )

if not ALLOWED_GUILD_IDS:
    raise ValueError("❌ ALLOWED_GUILD_IDS is empty. Add at least one server ID.")

# ← Authorized users for admin commands
if not ALLOWED_USERS_STR:
    raise ValueError(
        "❌ Missing ALLOWED_USERS\n"
        "Configure it in Railway → Variables → ALLOWED_USERS\n"
        "Format: ID1,ID2,ID3 (separated by commas)\n"
        "Example: 123456789,987654321 (only these users can use /reset_cooldown and /reset_all_cooldowns)"
    )

try:
    ALLOWED_USERS = [int(uid.strip()) for uid in ALLOWED_USERS_STR.split(",") if uid.strip()]
except ValueError as e:
    raise ValueError(
        f"❌ ALLOWED_USERS invalid.\n"
        f"Use format: ID1,ID2,ID3\n"
        f"Example: 123456789,987654321\n"
        f"Error: {e}"
    )

if not ALLOWED_USERS:
    raise ValueError("❌ ALLOWED_USERS is empty. Add at least one user ID.")

TOKENS_FILE = Path("tokens.json")
COOLDOWNS_FILE = Path("cooldowns.json")

COOLDOWN_SECONDS = 1 * 60  # 20 minutos

# ---------------------------------------------------------------------------
# COOLDOWN MANAGEMENT
# ---------------------------------------------------------------------------
def load_cooldowns() -> dict:
    """Load cooldown data from file or initialize empty dict"""
    try:
        if COOLDOWNS_FILE.exists():
            content = COOLDOWNS_FILE.read_text()
            return json.loads(content)
    except (json.JSONDecodeError, FileNotFoundError):
        pass
    return {}


def save_cooldowns(cooldowns: dict) -> None:
    """Persist cooldown data to file"""
    try:
        COOLDOWNS_FILE.write_text(json.dumps(cooldowns, indent=2))
    except Exception as e:
        print(f"[BOT] ❌ Error saving cooldowns: {e}")


def check_cooldown(user_id: str) -> Tuple[bool, int]:
    """Check if user is on cooldown. Returns (is_on_cooldown, seconds_remaining)"""
    cooldowns = load_cooldowns()
    current_time = int(time.time())
    
    if user_id not in cooldowns:
        return False, 0
    
    last_used = cooldowns[user_id]
    elapsed = current_time - last_used
    
    if elapsed < COOLDOWN_SECONDS:
        remaining = COOLDOWN_SECONDS - elapsed
        return True, remaining
    
    return False, 0


def set_cooldown(user_id: str) -> None:
    """Record when user last used the command"""
    cooldowns = load_cooldowns()
    cooldowns[str(user_id)] = int(time.time())
    save_cooldowns(cooldowns)


def format_time_remaining(seconds: int) -> str:
    """Convert seconds to human-readable format"""
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}m {secs}s"


# ---------------------------------------------------------------------------
# TOKENS MANAGEMENT - MEJORADO
# ---------------------------------------------------------------------------
def load_tokens() -> dict:
    """Load tokens from file - SIEMPRE RECARGA DESDE DISCO"""
    try:
        if TOKENS_FILE.exists():
            content = TOKENS_FILE.read_text()
            tokens_data = json.loads(content)
            print(f"[BOT] 🔄 Tokens recargados desde {TOKENS_FILE}")
            return tokens_data
        else:
            raise FileNotFoundError(f"{TOKENS_FILE} no encontrado")
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"[BOT] ❌ Error cargando tokens: {e}")
        raise


def get_random_token() -> Tuple[str, str, str]:
    """
    Get a random token pair from the tokens list.
    SIEMPRE recarga el archivo primero para asegurar tokens frescos.
    Returns (token, refresh_token, token_id)
    """
    # ← CLAVE: Recarga SIEMPRE desde disco
    tokens_data = load_tokens()
    
    if "tokens" not in tokens_data or len(tokens_data["tokens"]) == 0:
        raise ValueError("No hay tokens disponibles en tokens.json")
    
    # Select random token
    random_token_data = random.choice(tokens_data["tokens"])
    
    token = random_token_data.get("token", "")
    refresh_token = random_token_data.get("refresh_token", "")
    token_id = random_token_data.get("id", "unknown")
    
    if not token or not refresh_token:
        raise ValueError(f"Token {token_id} tiene campos faltantes")
    
    return token, refresh_token, token_id


if not TOKENS_FILE.exists():
    raise ValueError(f"❌ {TOKENS_FILE} no encontrado. Por favor crea el archivo con los datos de tokens.")

# ---------------------------------------------------------------------------
# DISCORD BOT
# ---------------------------------------------------------------------------
intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


@tree.command(
    name="reset_cooldown",
    description="⚙️ Remove cooldown from a specific user (Authorized users only)"
)
async def reset_cooldown_cmd(interaction: discord.Interaction, user_id: str):
    """
    Command /reset_cooldown - Removes cooldown from a specific user
    
    ✨ AUTHORIZED USERS ONLY
    """
    try:
        if interaction.guild_id not in ALLOWED_GUILD_IDS:
            await interaction.response.send_message(
                "🚫 **Access Denied** - Unauthorized server",
                ephemeral=True,
            )
            return
        
        if interaction.user.id not in ALLOWED_USERS:
            await interaction.response.send_message(
                "🚫 **Access Denied**\n\n>>> You are not authorized to use this command.\n"
                f">>> Your User ID: `{interaction.user.id}`\n"
                f">>> Contact your server administrator.",
                ephemeral=True,
            )
            print(f"[BOT] 🚫 Unauthorized user {interaction.user} (ID: {interaction.user.id}) tried to reset cooldown")
            return
        
        cooldowns = load_cooldowns()
        
        if user_id not in cooldowns:
            await interaction.response.send_message(
                f"ℹ️ **User Not Found**\n\n>>> User `{user_id}` doesn't have an active cooldown.",
                ephemeral=True,
            )
            return
        
        # Remove cooldown
        del cooldowns[user_id]
        save_cooldowns(cooldowns)
        
        await interaction.response.send_message(
            f"✅ **Cooldown Removed**\n\n"
            f">>> User `{user_id}` cooldown has been cleared.\n"
            f">>> They can now use `/token` immediately.",
            ephemeral=True,
        )
        print(f"[BOT] ✅ Cooldown reset for user {user_id}")
        
    except Exception as e:
        await interaction.response.send_message(
            f"❌ **Error Resetting Cooldown**\n\n>>> `{str(e)}`",
            ephemeral=True,
        )
        print(f"[BOT] ❌ Error in /reset_cooldown command: {e}")
        traceback.print_exc()


@tree.command(
    name="reset_all_cooldowns",
    description="⚙️ Remove all cooldowns (Authorized users only)"
)
async def reset_all_cooldowns_cmd(interaction: discord.Interaction):
    """
    Command /reset_all_cooldowns - Removes all active cooldowns
    
    ✨ AUTHORIZED USERS ONLY
    """
    try:
        if interaction.guild_id not in ALLOWED_GUILD_IDS:
            await interaction.response.send_message(
                "🚫 **Access Denied** - Unauthorized server",
                ephemeral=True,
            )
            return
        
        if interaction.user.id not in ALLOWED_USERS:
            await interaction.response.send_message(
                "🚫 **Access Denied**\n\n>>> You are not authorized to use this command.\n"
                f">>> Your User ID: `{interaction.user.id}`\n"
                f">>> Contact your server administrator.",
                ephemeral=True,
            )
            print(f"[BOT] 🚫 Unauthorized user {interaction.user} (ID: {interaction.user.id}) tried to reset all cooldowns")
            return
        
        cooldowns = load_cooldowns()
        num_cooldowns = len(cooldowns)
        
        # Clear all cooldowns
        cooldowns.clear()
        save_cooldowns(cooldowns)
        
        await interaction.response.send_message(
            f"✅ **All Cooldowns Removed**\n\n"
            f">>> {num_cooldowns} cooldown(s) have been cleared.\n"
            f">>> All users can now use `/token` immediately.",
            ephemeral=True,
        )
        print(f"[BOT] ✅ All cooldowns reset ({num_cooldowns} users)")
        
    except Exception as e:
        await interaction.response.send_message(
            f"❌ **Error Resetting Cooldowns**\n\n>>> `{str(e)}`",
            ephemeral=True,
        )
        print(f"[BOT] ❌ Error in /reset_all_cooldowns command: {e}")
        traceback.print_exc()





@tree.command(
    name="token",
    description="Retrieve current session token (Only in authorized servers)"
)
async def token_cmd(interaction: discord.Interaction):
    """
    Command /token - Retrieves random Nakama session token
    
    ✨ RANDOM TOKEN DISTRIBUTION FROM POOL
    ✨ SIEMPRE RECARGA TOKENS FRESCOS DESDE DISCO
    """
    try:
        # Validation: Check if server is authorized
        if interaction.guild_id not in ALLOWED_GUILD_IDS:
            guild_list = ", ".join(f"`{gid}`" for gid in ALLOWED_GUILD_IDS)
            await interaction.response.send_message(
                f"🚫 **Access Denied**\n\n"
                f">>> This command is only available in authorized servers.\n"
                f">>> Authorized servers: {guild_list}\n"
                f">>> Your server ID: `{interaction.guild_id}`",
                ephemeral=True,
            )
            print(f"[BOT] 🚫 Unauthorized access attempt from {interaction.user} in guild {interaction.guild_id}")
            return
        
        # Check cooldown
        user_id = str(interaction.user.id)
        is_on_cooldown, time_remaining = check_cooldown(user_id)
        
        if is_on_cooldown:
            time_str = format_time_remaining(time_remaining)
            await interaction.response.send_message(
                f"⏱️ **Cooldown Active**\n\n"
                f">>> You can use this command again in: **`{time_str}`**\n"
                f">>> 🔒 *1-minute cooldown so bot doesnt broke*",
                ephemeral=True,
            )
            print(f"[BOT] ⏱️ Cooldown blocked {interaction.user} ({time_remaining}s remaining)")
            return
        
        if not TOKENS_FILE.exists():
            await interaction.response.send_message(
                "❌ **Token file not found**\n\n"
                ">>> Tokens will be available shortly. Please try again in a moment.",
                ephemeral=True,
            )
            return

        try:
            # 🔄 CLAVE: Recarga SIEMPRE los tokens frescos desde disco
            token, refresh_token, token_id = get_random_token()
        except ValueError as e:
            await interaction.response.send_message(
                f"❌ **Token Error**\n\n>>> {str(e)}",
                ephemeral=True,
            )
            return
        
        # Set cooldown after successful retrieval
        set_cooldown(user_id)
        
        message = (
            f"╔══════════════════════════════════════╗\n"
            f"║        TOKEN GENERATOR               ║\n"
            f"╚══════════════════════════════════════╝\n\n"
            f"**Token ID:** `{token_id}`\n\n"
            f"**Bearer Token:**\n"
            f"```{token}```\n\n"
            f"**Refresh Token:**\n"
            f"```{refresh_token}```\n\n"
            f"───────────────────────────────────────\n"
            f" **Next available:** `1 minute`\n"
            f" **Status:** `Active `\n"
            f" **Distribution:** `Plswork`\n"
            f" **Refresh:** `AUTOMATIC (every 60s)`\n"
            f"───────────────────────────────────────\n\n"
            f">>> * token gen* **made by t.deo**"
        )

        await interaction.response.send_message(message, ephemeral=True)
        print(f"[BOT] ✅ Token {token_id} retrieved by {interaction.user} | Next cooldown: 20 min")
        
    except json.JSONDecodeError:
        await interaction.response.send_message(
            "❌ **Invalid JSON Format**\n\n"
            ">>> The token file is corrupted. Contact admin for assistance.",
            ephemeral=True,
        )
    except Exception as e:
        await interaction.response.send_message(
            f"❌ **Error Retrieving Tokens**\n\n"
            f">>> `{str(e)}`",
            ephemeral=True,
        )
        print(f"[BOT] ❌ Error in /token command: {e}")
        traceback.print_exc()


@client.event
async def on_ready():
    """Executes when bot connects successfully"""
    try:
        await tree.sync()
        
        # Count available tokens
        try:
            tokens_data = load_tokens()
            token_count = len(tokens_data.get("tokens", []))
        except:
            token_count = 0
        
        print(f"\n{'='*60}")
        print(f"✅ Bot connected as: {client.user}")
        print(f"✅ Commands available:")
        print(f"   • /token (Get Nakama session token)")
        print(f"   • /reset_cooldown (Admin only)")
        print(f"   • /reset_all_cooldowns (Admin only)")
        print(f"✅ Available tokens: {token_count}")
        print(f"✅ Authorized servers (Guild IDs):")
        for guild_id in ALLOWED_GUILD_IDS:
            print(f"   • {guild_id}")
        print(f"✅ Authorized users for admin commands (User IDs):")
        for user_id in ALLOWED_USERS:
            print(f"   • {user_id}")
        print(f"✅ 20-minute cooldown per user")
        print(f"✅ 🔄 Automatic token refresh: ENABLED (every 60 seconds)")
        print(f"{'='*60}\n")
    except Exception as e:
        print(f"[BOT] ❌ Error in on_ready: {e}")
        traceback.print_exc()


@client.event
async def on_error(event, *args, **kwargs):
    """Handle event errors"""
    print(f"[BOT] ❌ Error in event '{event}':")
    traceback.print_exc()


@client.event
async def on_disconnect():
    """Executes when bot disconnects"""
    print("[BOT] ⚠️ Bot disconnected from Discord")


@client.event
async def on_resumed():
    """Executes when bot reconnects"""
    print("[BOT] ✅ Bot reconnected to Discord")


if __name__ == "__main__":
    try:
        print("[BOT] Starting Discord bot...")
        print(f"[BOT] Authorized servers: {ALLOWED_GUILD_IDS}")
        print(f"[BOT] Authorized users (for admin commands): {ALLOWED_USERS}")
        print(f"[BOT] Mode: SINGLE TOKEN MODE (1 token para todos)")
        print(f"[BOT] 🔄 Token se refresca AUTOMATICAMENTE cada 60 segundos\n")
        client.run(BOT_TOKEN)
    except Exception as e:
        print(f"[BOT] ❌ Fatal error: {e}")
        traceback.print_exc()
