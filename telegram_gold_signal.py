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

CONFIG_FILE = os.environ.get("CONFIG_FILE", os.path.expanduser("~/.gemini/config/forex_telegram_config.json"))
STATE_FILE = os.environ.get("STATE_FILE", os.path.expanduser("~/.gemini/config/forex_signal_state.json"))

def load_state() -> dict:
    """Loads previous signal state safely."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"[!] Warning reading state file: {e}")
    return {}

def save_state(signal: str, price: float, timestamp: str):
    """Safely saves current signal state ensuring parent directory exists."""
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump({
                "signal": signal,
                "price": price,
                "timestamp": timestamp
            }, f, indent=2)
    except Exception as e:
        print(f"[!] Warning saving state file ({e})")

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
    Returns True if current UTC time is within active market sessions.
    - Asian / Tokyo Session: 00:00 - 06:00 UTC (05:30 AM - 11:30 AM IST)
    - London Morning Session: 06:00 - 12:00 UTC (11:30 AM - 05:30 PM IST)
    - London / New York Overlap (Peak Liquidity): 12:00 - 16:30 UTC (05:30 PM - 10:00 PM IST)
    - New York Afternoon Session: 16:30 - 21:00 UTC (10:00 PM - 02:30 AM IST)
    - Sydney / Asian Open: 22:00 - 24:00 UTC (03:30 AM - 05:30 AM IST)
    - Daily Rollover Window: 21:00 - 22:00 UTC (spread widening caution)
    - Weekend: Saturday (all day) & Sunday (until 22:00 UTC Asian open)
    """
    now_utc = datetime.now(timezone.utc)
    hour = now_utc.hour + now_utc.minute / 60.0
    weekday = now_utc.weekday()
    
    # Saturday is fully closed
    if weekday == 5:
        return False, "Market Closed (Saturday)"
        
    # Sunday before Asian open (22:00 UTC) is closed
    if weekday == 6 and hour < 22.0:
        return False, "Market Closed (Sunday Pre-Open)"
        
    # Friday after 21:30 UTC is market close
    if weekday == 4 and hour >= 21.5:
        return False, "Market Closed (Weekend Close)"
        
    if 0.0 <= hour < 6.0:
        return True, "Asian / Tokyo Session"
    elif 6.0 <= hour < 12.0:
        return True, "London Morning Session"
    elif 12.0 <= hour < 16.5:
        return True, "London / New York Overlap (Peak Liquidity)"
    elif 16.5 <= hour < 21.0:
        return True, "New York Afternoon Session"
    elif 22.0 <= hour <= 24.0:
        return True, "Sydney / Asian Open"
    else:
        return False, "Daily Market Rollover (21:00-22:00 UTC spread spike)"

def is_india_market_window():
    """
    Returns True if current time is within India market monitoring hours:
    10:00 AM IST to 10:00 PM IST (UTC+5:30), Monday through Friday.
    """
    try:
        from zoneinfo import ZoneInfo
        now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
    except Exception:
        from datetime import timedelta
        now_ist = datetime.now(timezone(timedelta(hours=5, minutes=30)))

    weekday = now_ist.weekday()  # 0=Monday, 4=Friday, 5=Saturday, 6=Sunday
    hour_val = now_ist.hour + now_ist.minute / 60.0
    time_str = now_ist.strftime("%H:%M:%S IST")

    if weekday == 5:
        return False, f"Market Closed (Saturday) @ {time_str}"
    if weekday == 6:
        return False, f"Market Closed (Sunday) @ {time_str}"

    if 10.0 <= hour_val <= 22.0:
        return True, f"India Market Window ({time_str} is within 10:00 AM - 10:00 PM IST)"
    
    return False, f"Outside India Market Window ({time_str} is outside 10:00 AM - 10:00 PM IST)"

def format_telegram_alert(res: dict, session_name: str) -> str:
    """Formats the signal analysis into a professional, mobile-friendly Telegram alert."""
    sig = res["signal"]
    icon = "🟢" if "BUY" in sig else ("🔴" if "SELL" in sig else "🟡")
    
    ex = res["execution"]
    ind = res["indicators"]
    p = res.get("pivots_daily", {})
    tf = res.get("timeframe", "SMC (15M Execution / 1H Structure)")
    src = res.get("price_source", "Spot XAU/USD Live")
    
    lines = [
        f"{icon} *{sig} ALERT: XAU/USD (Gold)*",
        f"⏱ *Mode*: `{tf}` | *Session*: {session_name}",
        f"🕒 *Time*: `{res['timestamp']}`",
        f"💵 *Live Spot CMP*: `${res['current_price']:.2f}` ({src})",
        f"🎯 *Confidence*: `{res['confidence_percent']}%` | *Bias*: `{res['bias']}`"
    ]
    
    if res.get("entry_reason"):
        lines.append(f"🏛 *SMC Setup*: `{res['entry_reason']}`")
        
    dr = res.get("dealing_range")
    if dr:
        regime = "PREMIUM (Sell Zone)" if "SELL" in sig else ("DISCOUNT (Buy Zone)" if "BUY" in sig else "EQUILIBRIUM")
        lines.append(f"⚖️ *Dealing Range*: `${dr['range_low']} – ${dr['range_high']}` (50% Eq: `${dr['equilibrium_50']}` | `{regime}`)")
        
    lines.extend([
        "",
        "───────────────",
        "📋 *EXECUTION PLAN*",
        f"• *Action*: `{res['bias']}`",
        f"• *Entry Zone (CMP)*: `{ex['entry_range']}`",
        f"• *Stop Loss*: `{ex['stop_loss']}` (Risk: `{ex['risk_per_ounce']}/oz` - Structural)",
        f"• *Target 1 (TP1)*: `{ex['take_profit_1']}`",
        f"• *Target 2 (TP2)*: `{ex['take_profit_2']}`",
        f"• *Target 3 (TP3)*: `{ex['take_profit_3']}`",
        f"• *Rule*: _{ex['trade_management']}_",
        "───────────────"
    ])
    
    fr = ex.get("free_roll_protocol")
    if fr:
        lines.extend([
            "",
            "🛡️ *ZERO-DOWNSIDE FREE-ROLL PROTOCOL*",
            f"1️⃣ {fr.get('step_1')}",
            f"2️⃣ {fr.get('step_2')}",
            f"3️⃣ {fr.get('step_3')}",
            f"★ _{fr.get('guarantee')}_",
            "───────────────"
        ])
        
    toolkit = ex.get("live_account_toolkit")
    if toolkit:
        pos = toolkit.get("position_sizing_table", {})
        lines.extend([
            "",
            "💼 *LIVE ACCOUNT LOT SIZES (1% STRICT RISK)*",
            f"• `$500` Balance ──► `{pos.get('$500', {}).get('recommended_lots', '0.01')} Lots`",
            f"• `$1,000` Balance ──► `{pos.get('$1,000', {}).get('recommended_lots', '0.02')} Lots`",
            f"• `$5,000` Balance ──► `{pos.get('$5,000', {}).get('recommended_lots', '0.11')} Lots`",
            f"• `$10,000` Balance ──► `{pos.get('$10,000', {}).get('recommended_lots', '0.22')} Lots`",
            f"🛡️ _{toolkit.get('broker_spread_guard')}_",
            "───────────────"
        ])
        
    lines.extend([
        "",
        "📊 *KEY CONFLUENCE*"
    ])
    
    if "atr_14_15m" in ind:
        lines.extend([
            f"• 15M RSI: `{ind.get('rsi_14_15m')}` | 15M ATR: `${ind.get('atr_14_15m')}`",
            f"• 15M EMAs: 20: `${ind.get('ema_20_15m')}` | 50: `${ind.get('ema_50_15m')}`",
            f"• 1H Macro Trend: `{ind.get('h1_trend')}` (50 EMA `${ind.get('h1_ema_50')}` | 200 EMA `${ind.get('h1_ema_200')}`)",
            f"• US Dollar Index (DXY): `{ind.get('dxy_trend')}` ({ind.get('dxy_price')})"
        ])
    elif "atr_14_5m" in ind:
        lines.extend([
            f"• 5M RSI: `{ind.get('rsi_14_5m')}` | 15M RSI: `{ind.get('rsi_14_15m')}` | 5M ATR: `${ind.get('atr_14_5m')}`",
            f"• 5M EMAs: 9: `${ind.get('ema_9_5m')}` | 21: `${ind.get('ema_21_5m')}` | 50: `${ind.get('ema_50_5m')}`",
            f"• 15M Trend: 20 EMA `${ind.get('ema_20_15m')}` | 50 EMA `${ind.get('ema_50_15m')}`",
            f"• US Dollar Index (DXY): `{ind.get('dxy_trend')}` ({ind.get('dxy_price')})"
        ])
    else:
        lines.extend([
            f"• 1H RSI: `{ind.get('rsi_14_1h')}` | Daily RSI: `{ind.get('rsi_14_daily')}`",
            f"• 1H 200 EMA: `${ind.get('ema_200_1h')}` | 1H 50 EMA: `${ind.get('ema_50_1h')}`",
            f"• Daily Pivot (PP): `${p.get('PP')}` | S1: `${p.get('S1')}` | R1: `${p.get('R1')}`",
            f"• US Dollar Index (DXY): `{ind.get('dxy_trend')}` ({ind.get('dxy_price')})"
        ])
        
    lines.extend([
        "",
        "⚠️ _Gold carries high volatility. Size strictly at 1-2% account equity risk._"
    ])
    return "\n".join(lines)

def run_check(force: bool = False, timeframe: str = "smc", check_india_window: bool = True) -> bool:
    """Executes a single check and sends alert if criteria are met."""
    config = load_config()
    bot_token = config.get("bot_token")
    chat_id = config.get("chat_id")
    
    if not bot_token or not chat_id:
        print("[!] Telegram credentials not configured. Run with --setup first.")
        return False

    if check_india_window and not force:
        is_india_open, india_status = is_india_market_window()
        if not is_india_open:
            print(f"[-] {india_status}. Skipping check.")
            return False

    is_active, session_name = is_active_session()
    if config.get("check_sessions_only", True) and not is_active and not force:
        print(f"[-] Current time is outside prime sessions: {session_name}. Skipping check.")
        return False
        
    print(f"[*] Analyzing Gold market in {timeframe.upper()} mode during {session_name}...")
    res = analyze_gold(timeframe_mode=timeframe)
    confidence = res.get("confidence_percent", 0)
    signal = res.get("signal", "NEUTRAL")
    
    print(f"[*] Engine result: {signal} ({confidence}% confidence)")
    
    # Verify strict filter criteria (bypassed if --force is explicitly requested)
    if not force and (confidence < config.get("min_confidence", 70) or "NEUTRAL" in signal or "PATIENCE" in signal):
        print(f"[-] No high-probability setup met (Confidence {confidence}% < {config.get('min_confidence', 70)}% or Neutral/Patience).")
        return False
        
    # Check state file to prevent duplicate alerts
    last_state = load_state()
            
    last_sig = last_state.get("signal")
    last_price = last_state.get("price", 0)
    curr_price = res["current_price"]
    
    # In SMC/Scalping, a $1.50+ move is a fresh entry zone; in swing, $6.0+
    min_price_move = 1.50 if timeframe in ("smc", "scalp", "intraday") else 6.0
    last_time_str = last_state.get("timestamp", "")
    time_elapsed_min = 999.0
    if last_time_str:
        try:
            t_last = datetime.strptime(last_time_str, "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)
            time_elapsed_min = (datetime.now(timezone.utc) - t_last).total_seconds() / 60.0
        except Exception:
            pass
            
    # Send if:
    # 1. Force is enabled
    # 2. Signal direction changed (e.g. BUY -> SELL)
    # 3. Price moved by $1.50+ (fresh entry zone)
    # 4. At least 15 minutes elapsed since last alert and setup remains active
    if not force and last_sig == signal and abs(curr_price - last_price) < min_price_move and time_elapsed_min < 15.0:
        print(f"[-] Active {signal} setup at ${curr_price:.2f} (price moved ${abs(curr_price - last_price):.2f} < ${min_price_move}, last alert {time_elapsed_min:.1f}m ago). Skipping duplicate.")
        return False
        
    # Send alert
    msg = format_telegram_alert(res, session_name)
    success = send_telegram_message(bot_token, chat_id, msg)
    if success:
        # Save state safely
        save_state(signal, curr_price, res["timestamp"])
    return success

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Telegram Gold Signal Broadcaster")
    parser.add_argument("--setup", action="store_true", help="Configure Bot Token and Chat ID")
    parser.add_argument("--token", type=str, help="Telegram Bot Token")
    parser.add_argument("--chat-id", type=str, help="Telegram Chat ID")
    parser.add_argument("--test", action="store_true", help="Send a test message to Telegram")
    parser.add_argument("--force", action="store_true", help="Run analysis regardless of session hours")
    parser.add_argument("--timeframe", choices=["smc", "scalp", "intraday", "swing"], default="smc", help="Signal timeframe mode (default: smc - Institutional Order Block & FVG)")
    parser.add_argument("--interval", type=int, default=300, help="Daemon check interval in seconds (default: 300 = 5 minutes)")
    parser.add_argument("--daemon", action="store_true", help="Run continuous loop (checks every 5 minutes during trading sessions)")
    parser.add_argument("--no-india-window", action="store_true", help="Disable India market window enforcement (10:00 AM - 10:00 PM IST)")
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
        interval_sec = max(args.interval, 30)
        interval_min = interval_sec / 60.0
        print(f"[*] Starting Telegram Gold Signal daemon (checking every {interval_min:.1f} min / {interval_sec}s)...")
        while True:
            try:
                run_check(force=args.force, timeframe=args.timeframe, check_india_window=not args.no_india_window)
            except Exception as e:
                print(f"[!] Daemon error: {e}")
            time.sleep(interval_sec)
    else:
        run_check(force=args.force, timeframe=args.timeframe, check_india_window=not args.no_india_window)

if __name__ == "__main__":
    main()
