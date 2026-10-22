#!/usr/bin/env python3
"""
Telegram Forex Gold (XAU/USD) Automated Signal Broadcaster
Runs during London and New York sessions, evaluates Gold multi-timeframe confluence,
and broadcasts high-probability institutional setups directly to Telegram.
"""

import os
import sys
import json
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone

# Add parent directory to path to import gold_signal engine
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.append(script_dir)

from gold_signal import analyze_gold

CONFIG_FILE = os.path.expanduser("~/.gemini/config/forex_telegram_config.json")
STATE_FILE = os.path.expanduser("~/.gemini/config/forex_signal_state.json")

def load_config():
    """Loads Telegram Bot Token and Chat ID from config or environment."""
    config = {
        "bot_token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        "chat_id": os.environ.get("TELEGRAM_CHAT_ID", ""),
        "min_confidence": 70,
        "check_sessions_only": True
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                saved = json.load(f)
                config.update(saved)
        except Exception as e:
            print(f"[!] Warning reading config file: {e}")
    return config

def save_config(bot_token: str, chat_id: str, min_confidence: int = 70):
    """Saves Telegram configuration for persistent runs."""
    config = {
        "bot_token": bot_token.strip(),
        "chat_id": str(chat_id).strip(),
        "min_confidence": min_confidence,
        "check_sessions_only": True
    }
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    print(f"[✓] Telegram configuration saved to {CONFIG_FILE}")

def send_telegram_message(bot_token: str, chat_id: str, text: str) -> bool:
    """Sends a markdown message to a Telegram chat or channel."""
    if not bot_token or not chat_id:
        print("[!] Error: Telegram bot_token or chat_id is missing.")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    
    try:
        data = urllib.parse.urlencode(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            res_data = json.loads(resp.read().decode())
            if res_data.get("ok"):
                print("[✓] Telegram message successfully sent!")
                return True
            else:
                print(f"[!] Telegram API error: {res_data}")
                return False
    except Exception as e:
        print(f"[!] Failed to send Telegram message: {e}")
        return False

def is_active_session():
    """
    Returns True if current UTC time is within high-probability London or NY sessions.
    - London Session: 07:00 - 10:30 UTC (12:30 PM - 4:00 PM IST)
    - NY / Overlap: 12:00 - 17:00 UTC (5:30 PM - 10:30 PM IST)
    """
    now_utc = datetime.now(timezone.utc)
    hour = now_utc.hour + now_utc.minute / 60.0
    
    # Exclude weekend
    if now_utc.weekday() in (5, 6): # Saturday, Sunday
        return False, "Market Closed (Weekend)"
        
    in_london = 7.0 <= hour <= 10.5
    in_ny = 12.0 <= hour <= 17.0
    
    if in_london:
        return True, "London Open Session"
    elif in_ny:
        return True, "New York / London Overlap Session"
    else:
        return False, "Outside Prime Sessions (Asian / Off-hours)"

def format_telegram_alert(res: dict, session_name: str) -> str:
    """Formats the signal analysis into a professional, mobile-friendly Telegram alert."""
    sig = res["signal"]
    icon = "🟢" if "BUY" in sig else ("🔴" if "SELL" in sig else "🟡")
    
    ex = res["execution"]
    ind = res["indicators"]
    p = res["pivots_daily"]
    
    lines = [
        f"{icon} *{sig} ALERT: XAU/USD (Gold)*",
        f"⏱ *Session*: {session_name} | `{res['timestamp']}`",
        f"💵 *Current Price*: `${res['current_price']:.2f}`",
        f"🎯 *Confidence*: `{res['confidence_percent']}%` | *Bias*: `{res['bias']}`",
        "",
        "───────────────",
        "📋 *EXECUTION PLAN*",
        f"• *Action*: `{res['bias']}`",
        f"• *Entry Zone*: `{ex['entry_range']}`",
        f"• *Stop Loss*: `{ex['stop_loss']}` (Risk: `{ex['risk_per_ounce']}/oz`)",
        f"• *Target 1 (TP1)*: `{ex['take_profit_1']}`",
        f"• *Target 2 (TP2)*: `{ex['take_profit_2']}`",
        f"• *Target 3 (TP3)*: `{ex['take_profit_3']}`",
        f"• *Rule*: _{ex['trade_management']}_",
        "───────────────",
        "",
        "📊 *KEY CONFLUENCE*",
        f"• 1H RSI: `{ind['rsi_14_1h']}` | Daily RSI: `{ind['rsi_14_daily']}`",
        f"• 1H 200 EMA: `${ind['ema_200_1h']}` | 1H 50 EMA: `${ind['ema_50_1h']}`",
        f"• Daily Pivot (PP): `${p.get('PP')}` | S1: `${p.get('S1')}` | R1: `${p.get('R1')}`",
        f"• US Dollar Index (DXY): `{ind['dxy_trend']}` ({ind['dxy_price']})",
        "",
        "⚠️ _Gold carries high volatility. Size strictly at 1-2% account equity risk._"
    ]
    return "\n".join(lines)

def run_check(force: bool = False, timeframe: str = "swing") -> bool:
    """Executes a single check and sends alert if criteria are met."""
    config = load_config()
    bot_token = config.get("bot_token")
    chat_id = config.get("chat_id")
    
    if not bot_token or not chat_id:
        print("[!] Telegram credentials not configured. Run with --setup first.")
        return False
        
    is_active, session_name = is_active_session()
    if config.get("check_sessions_only", True) and not is_active and not force:
        print(f"[-] Current time is outside prime sessions: {session_name}. Skipping check.")
        return False
        
    print(f"[*] Analyzing Gold market during {session_name}...")
    res = analyze_gold(timeframe_mode=timeframe)
    confidence = res.get("confidence_percent", 0)
    signal = res.get("signal", "NEUTRAL")
    
    print(f"[*] Engine result: {signal} ({confidence}% confidence)")
    
    # Verify strict filter criteria
    if confidence < config.get("min_confidence", 70) or "NEUTRAL" in signal:
        print(f"[-] No high-probability setup met (Confidence {confidence}% < {config.get('min_confidence', 70)}% or Neutral).")
        return False
        
    # Check state file to prevent duplicate alerts
    last_state = {}
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                last_state = json.load(f)
        except Exception:
            pass
            
    last_sig = last_state.get("signal")
    last_price = last_state.get("price", 0)
    curr_price = res["current_price"]
    
    # If same signal and price has moved less than $10, don't spam
    if not force and last_sig == signal and abs(curr_price - last_price) < 10.0:
        print("[-] Signal unchanged and price within $10 of last alert. Skipping to avoid spam.")
        return False
        
    # Send alert
    msg = format_telegram_alert(res, session_name)
    success = send_telegram_message(bot_token, chat_id, msg)
    if success:
        # Save state
        with open(STATE_FILE, "w") as f:
            json.dump({
                "signal": signal,
                "price": curr_price,
                "timestamp": res["timestamp"]
            }, f)
    return success

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Telegram Gold Signal Broadcaster")
    parser.add_argument("--setup", action="store_true", help="Configure Bot Token and Chat ID")
    parser.add_argument("--token", type=str, help="Telegram Bot Token")
    parser.add_argument("--chat-id", type=str, help="Telegram Chat ID")
    parser.add_argument("--test", action="store_true", help="Send a test message to Telegram")
    parser.add_argument("--force", action="store_true", help="Run analysis regardless of session hours")
    parser.add_argument("--timeframe", choices=["scalp", "intraday", "swing"], default="swing", help="Signal timeframe mode")
    parser.add_argument("--daemon", action="store_true", help="Run continuous loop (checks every 15 minutes during prime sessions)")
    args = parser.parse_args()
    
    if args.setup or (args.token and args.chat_id):
        token = args.token
        chat = args.chat_id
        if not token:
            token = input("Enter your Telegram Bot Token: ").strip()
        if not chat:
            chat = input("Enter your Telegram Chat ID: ").strip()
        save_config(token, chat)
        
    if args.test:
        config = load_config()
        if not config.get("bot_token") or not config.get("chat_id"):
            print("[!] Please configure bot_token and chat_id first using --setup or --token and --chat-id")
            sys.exit(1)
        test_msg = "🔔 *XAU/USD Gold Signal Bot Connected!*\n\nYour Telegram alerts are successfully configured. You will receive institutional buy/sell swing signals during London & New York session prime hours."
        send_telegram_message(config["bot_token"], config["chat_id"], test_msg)
        sys.exit(0)
        
    if args.daemon:
        print("[*] Starting Telegram Gold Signal daemon (checking every 15 min during London/NY)...")
        while True:
            try:
                run_check(force=args.force, timeframe=args.timeframe)
            except Exception as e:
                print(f"[!] Daemon error: {e}")
            time.sleep(900) # 15 minutes
    else:
        run_check(force=args.force, timeframe=args.timeframe)

if __name__ == "__main__":
    main()
