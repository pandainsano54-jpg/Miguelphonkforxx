"""
Main Entry Point - Runs Discord Bot + Token Refresher + Token Generator in Parallel
====================================================================================

Executes:
1. token_bot.py (Discord bot)
2. refresh_token.py --loop (token refresh loop every 60 seconds)
3. auto_token_generator.py --loop (generates new tokens every X hours)

All run concurrently using threading.
"""

import threading
import subprocess
import sys

def run_bot():
    """Execute Discord bot"""
    print("[MAIN] Starting Discord bot...")
    try:
        subprocess.run([sys.executable, "token_bot.py"], check=False)
    except Exception as e:
        print(f"[ERROR] Bot failed: {e}")

def run_refresh():
    """Execute token refresher in loop"""
    print("[MAIN] Starting token refresher...")
    try:
        subprocess.run([sys.executable, "refresh_token.py", "--loop"], check=False)
    except Exception as e:
        print(f"[ERROR] Refresher failed: {e}")

def run_generator():
    """Execute token generator in loop"""
    print("[MAIN] Starting auto token generator...")
    try:
        subprocess.run([sys.executable, "auto_token_generator.py", "--loop"], check=False)
    except Exception as e:
        print(f"[ERROR] Generator failed: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 DISCORD BOT + TOKEN REFRESH + AUTO GENERATOR")
    print("=" * 60)
    
    # Create threads for parallel execution
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    refresh_thread = threading.Thread(target=run_refresh, daemon=True)
    generator_thread = threading.Thread(target=run_generator, daemon=True)
    
    # Start all three
    bot_thread.start()
    refresh_thread.start()
    generator_thread.start()
    
    print("[MAIN] ✅ Bot, refresher, and generator started")
    
    # Keep program running
    try:
        bot_thread.join()
        refresh_thread.join()
        generator_thread.join()
    except KeyboardInterrupt:
        print("[MAIN] ❌ User interrupted")
        sys.exit(0)
