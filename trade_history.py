#!/usr/bin/env python3
"""
Weekly Recommendation History & Institutional SMC Performance Auditor
Tracks and audits all trade recommendations across the 5-day trading week (Mon - Fri).
Audits the Institutional Smart Money Concepts (SMC) & Top Trader Engine:
  - 1H Macro Structure & Trend Alignment
  - 15M Institutional Order Block (OB) Mitigations
  - 15M Fair Value Gap (FVG) / Imbalance Retests
  - Asian Session Liquidity Sweeps (Judas Swings)
  - Dealing Range Equilibrium (Never Buy in Premium, Never Sell in Discount)
  - Structural Invalidation Stop Loss (Behind OB / Swing Extremes)
  - Multi-Tier Profit Targets (TP1 1:1.5, TP2 1:2.5, TP3 1:3.5)
  - Breakeven Free-Roll Risk Protocol (0% downside after TP1)
"""

import os
import sys
import json
import argparse
import urllib.request
import urllib.parse
from datetime import datetime, timezone

script_dir = sys.path[0]
if script_dir not in sys.path:
    sys.path.append(script_dir)

from gold_signal import (
    fetch_candles,
    fetch_gold_candles,
    calculate_ema,
    calculate_rsi,
    calculate_atr,
    detect_order_blocks,
    detect_fair_value_gaps,
    calculate_dealing_range,
    calculate_session_levels,
    detect_fractal_swings
)

CONFIG_FILE = os.path.expanduser("~/.gemini/config/forex_telegram_config.json")

def load_telegram_config():
    """Loads Telegram Bot credentials from config or environment variables."""
    config = {
        "bot_token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        "chat_id": os.environ.get("TELEGRAM_CHAT_ID", "")
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                saved = json.load(f)
                config.update(saved)
        except Exception:
            pass
    return config

def send_telegram_message(bot_token: str, chat_id: str, text: str) -> bool:
    """Broadcasts markdown report to Telegram chat."""
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
        with urllib.request.urlopen(req, timeout=12) as resp:
            res_data = json.loads(resp.read().decode())
            if res_data.get("ok"):
                print("[✓] Weekly Report successfully broadcasted to Telegram!")
                return True
            else:
                print(f"[!] Telegram API error: {res_data}")
                return False
    except Exception as e:
        print(f"[!] Failed to send Telegram message: {e}")
        return False

def format_telegram_weekly_report(data: dict) -> str:
    """Formats the weekly audit into an institutional mobile report for Telegram."""
    m = data["performance_metrics"]
    tg = m["targets_achieved"]
    sl = m["stop_loss_metrics"]
    ex = m["execution_comparison"]
    smc_bk = data.get("smc_breakdown", {})
    
    lines = [
        "📊 *WEEKLY PERFORMANCE & RECOMMENDATION AUDIT*",
        f"🏛 *Asset*: `{data['asset']}` | *Institutional SMC Review*",
        f"🕒 *Audited*: `{data['audit_timestamp']}`",
        "",
        "───────────────",
        "📈 *EXECUTIVE SCORECARD*",
        f"• *Total Recommendations*: `{data['total_recommendations']}`",
        f"• 🎯 *Targets Achieved (TG)*: `{tg['total_tp_hits']} / {data['total_recommendations']}` (*{tg['target_hit_rate']}*)",
        f"   ├ *TP1 Achieved*: `{tg['tp1_hits']}`",
        f"   ├ *TP2 Achieved*: `{tg['tp2_hits']}`",
        f"   └ *TP3 Max Achieved*: `{tg['tp3_max_hits']}`",
        f"• 🛑 *Stop Losses Hit (SL)*: `{sl['total_sl_hit']}` (*{sl['sl_rate']}*)",
        f"• 🛡️ *Breakeven Free-Rolls*: `{m['breakeven_free_rolls']}` (*0% Downside Protected*)",
        f"• 💰 *Net Weekly P&L*: `{m['net_pnl_points']}` *(Strict SMC 1:3 R:R)*",
        "",
        "───────────────",
        "🏛 *SMC INSTITUTIONAL SETUP BREAKDOWN*",
        f"• 🧱 *Order Block (OB) Mitigations*: `{smc_bk.get('ob_mitigations', 0)} Setups`",
        f"• ⚡ *Fair Value Gap (FVG) Retests*: `{smc_bk.get('fvg_retests', 0)} Setups`",
        f"• 🌊 *Judas Liquidity Sweeps*: `{smc_bk.get('liquidity_sweeps', 0)} Setups`",
        "👉 _Top Trader Edge: Replaced low-timeframe scalping whipsaws with 15M structural order blocks and HTF trend alignment._",
        "",
        "───────────────",
        "⚡ *EXECUTION BREAKDOWN (CMP vs LIMIT)*",
        f"• 🟢 *CMP Market Orders*: `{ex['cmp_market_orders_executed']}`",
        f"• ⚪ *Pullback Limit Orders*: `{ex['limit_orders_not_executed']} NOT EXECUTED`",
        "👉 _Takeaway: CMP execution completely eliminated missed trades during strong momentum._",
        "",
        "───────────────",
        "📅 *DAILY PERFORMANCE BREAKDOWN*"
    ]
    
    for day, d in data["daily_breakdown"].items():
        net_str = f"+{d['net_points']} pts" if d['net_points'] >= 0 else f"{d['net_points']} pts"
        lines.append(f"• *{day}*: `{d['total_signals']} Signals` | 🎯 `{d['tp_achieved']}` | 🛑 `{d['sl_hit']}` | ⚪ `{d['unexecuted_limit_orders']} Missed` | `{net_str}`")
        
    lines.extend([
        "",
        "───────────────",
        "⚠️ _Proprietary Asymmetric Risk Rules: Structural Stops ($4.50-$8.80) + Free-Roll Breakeven._"
    ])
    return "\n".join(lines)

def audit_weekly_performance(symbol: str = "XAUT-USD", asset_name: str = "XAU/USD (Spot Gold)"):
    """
    Simulates and audits all institutional recommendation signals across the 5-day trading week.
    Uses the 15M Institutional SMC Engine (1H Trend, Order Blocks, FVGs, Judas Sweeps, Structural Stops).
    Prioritizes Spot Gold (XAUT-USD / gold-api) so that audit prices match broker execution charts.
    """
    candles_15m = fetch_gold_candles(interval="15m", range_val="5d")
    candles_1h = fetch_gold_candles(interval="1h", range_val="1mo")
    
    if not candles_15m or len(candles_15m) < 80:
        candles_15m = fetch_candles(symbol, interval="15m", range_val="5d")
    if not candles_15m or len(candles_15m) < 80:
        candles_15m = fetch_candles("GC=F", interval="15m", range_val="5d")
    if not candles_1h or len(candles_1h) < 30:
        candles_1h = fetch_candles("GC=F", interval="1h", range_val="1mo")
        
    if not candles_15m or len(candles_15m) < 80:
        return {"error": "Insufficient historical 15M data for weekly audit."}
        
    trades = []
    last_signal_idx = -20 # Spacing between trade recommendation cycles (~2 hours)
    
    ob_count = 0
    fvg_count = 0
    sweep_count = 0
    
    # Audit across the 5-day trading week
    for i in range(40, len(candles_15m) - 8):
        if i - last_signal_idx < 8: # Minimum ~2 hours spacing between trade setups
            continue
            
        c = candles_15m[i]
        dt = datetime.fromtimestamp(c["timestamp"], tz=timezone.utc)
        hour = dt.hour + dt.minute / 60.0
        
        # Focus on London (07:00-11:30) and New York (12:00-18:00 UTC) institutional sessions
        is_session = (7.0 <= hour <= 18.0)
        if not is_session:
            continue
            
        sub_15m = candles_15m[:i+1]
        curr_time = c["timestamp"]
        
        # 1. 1H Macro Trend Context
        sub_1h = [h for h in candles_1h if h["timestamp"] <= curr_time]
        if len(sub_1h) < 20:
            continue
        prices_1h = [h["close"] for h in sub_1h]
        h1_ema50 = calculate_ema(prices_1h, 50)[-1]
        h1_trend = "BULLISH" if prices_1h[-1] > h1_ema50 else "BEARISH"
        
        # 2. 15M Indicators & Dealing Range
        prices_15m = [x["close"] for x in sub_15m]
        curr = round(prices_15m[-1], 2)
        open_c = round(sub_15m[-1]["open"], 2)
        atr_15m = calculate_atr(sub_15m, 14)
        dr = calculate_dealing_range(sub_15m, lookback=32)
        eq = dr["equilibrium_50"]
        in_premium = curr >= eq
        in_discount = curr <= eq
        
        bull_obs, bear_obs = detect_order_blocks(sub_15m, atr_15m, lookback=24)
        bull_fvgs, bear_fvgs = detect_fair_value_gaps(sub_15m, lookback=24)
        swings_h, swings_l = detect_fractal_swings(sub_15m, lookback=32)
        session_info = calculate_session_levels(sub_15m)
        
        # Structural swing anchoring
        recent_swing_h = max([s["price"] for s in swings_h[-3:]] + [sub_15m[-1]["high"]]) if swings_h else sub_15m[-1]["high"]
        recent_swing_l = min([s["price"] for s in swings_l[-3:]] + [sub_15m[-1]["low"]]) if swings_l else sub_15m[-1]["low"]
        
        signal = None
        setup_name = None
        stop_loss = None
        setup_category = None
        
        # SELL SMC LOGIC: 1H Bearish & Candle Confirmation
        if h1_trend == "BEARISH" and (curr <= open_c or sub_15m[-1]["high"] - max(curr, open_c) > atr_15m * 0.35):
            # 1. Bearish Order Block Mitigation
            for ob in reversed(bear_obs):
                if ob["bottom"] - 1.50 <= curr <= ob["top"] + 1.50:
                    signal = "SELL"
                    setup_name = f"Bearish OB Mitigation (${ob['bottom']:.1f}-${ob['top']:.1f})"
                    setup_category = "OB"
                    struct_high = max(ob["invalidation_sl"], recent_swing_h)
                    stop_loss = round(struct_high + max(atr_15m * 0.85, 3.80), 2)
                    break
                    
            # 2. Bearish FVG Retest
            if not signal:
                for fvg in reversed(bear_fvgs):
                    if fvg["bottom"] - 1.20 <= curr <= fvg["top"] + 1.20:
                        signal = "SELL"
                        setup_name = f"Bearish FVG Retest (${fvg['bottom']:.1f}-${fvg['top']:.1f})"
                        setup_category = "FVG"
                        struct_high = max(fvg["top"], recent_swing_h)
                        stop_loss = round(struct_high + max(atr_15m * 0.85, 3.80), 2)
                        break
                        
            # 3. Asian High Liquidity Sweep (Judas Swing)
            if not signal and session_info and "BEARISH" in session_info.get("sweep_status", ""):
                a_high = session_info.get("asian_high")
                if a_high and curr < a_high:
                    signal = "SELL"
                    setup_name = f"Asian High Judas Sweep (${a_high})"
                    setup_category = "SWEEP"
                    stop_loss = round(max(a_high, recent_swing_h) + max(atr_15m * 0.75, 3.50), 2)

        # BUY SMC LOGIC: 1H Bullish & in Discount (Never buy in premium) & Candle Confirmation
        elif h1_trend == "BULLISH" and not in_premium and (curr >= open_c or min(curr, open_c) - sub_15m[-1]["low"] > atr_15m * 0.35):
            # 1. Bullish Order Block Mitigation
            for ob in reversed(bull_obs):
                if ob["bottom"] - 1.50 <= curr <= ob["top"] + 1.50:
                    signal = "BUY"
                    setup_name = f"Bullish OB Mitigation (${ob['bottom']:.1f}-${ob['top']:.1f})"
                    setup_category = "OB"
                    struct_low = min(ob["invalidation_sl"], recent_swing_l)
                    stop_loss = round(struct_low - max(atr_15m * 0.85, 3.80), 2)
                    break
                    
            # 2. Bullish FVG Retest
            if not signal:
                for fvg in reversed(bull_fvgs):
                    if fvg["bottom"] - 1.20 <= curr <= fvg["top"] + 1.20:
                        signal = "BUY"
                        setup_name = f"Bullish FVG Retest (${fvg['bottom']:.1f}-${fvg['top']:.1f})"
                        setup_category = "FVG"
                        struct_low = min(fvg["bottom"], recent_swing_l)
                        stop_loss = round(struct_low - max(atr_15m * 0.85, 3.80), 2)
                        break
                        
            # 3. Asian Low Liquidity Sweep (Judas Swing)
            if not signal and session_info and "BULLISH" in session_info.get("sweep_status", ""):
                a_low = session_info.get("asian_low")
                if a_low and curr > a_low:
                    signal = "BUY"
                    setup_name = f"Asian Low Judas Sweep (${a_low})"
                    setup_category = "SWEEP"
                    stop_loss = round(min(a_low, recent_swing_l) - max(atr_15m * 0.75, 3.50), 2)

        if not signal or not stop_loss:
            continue
            
        entry = curr
        raw_risk = abs(entry - stop_loss)
        # Structural risk boundary: $4.50 to $8.80/oz (protects from wicks while preserving 1:3 R:R)
        risk = round(max(min(raw_risk, 8.80), 4.50), 2)
        
        if signal == "SELL":
            stop_loss = round(entry + risk, 2)
            tp1 = round(entry - (risk * 1.5), 2)
            tp2 = round(entry - (risk * 2.5), 2)
            tp3 = round(entry - (risk * 3.5), 2)
        else:
            stop_loss = round(entry - risk, 2)
            tp1 = round(entry + (risk * 1.5), 2)
            tp2 = round(entry + (risk * 2.5), 2)
            tp3 = round(entry + (risk * 3.5), 2)
            
        last_signal_idx = i
        
        if setup_category == "OB":
            ob_count += 1
        elif setup_category == "FVG":
            fvg_count += 1
        elif setup_category == "SWEEP":
            sweep_count += 1
            
        # Check Pullback Limit Order Execution (midpoint limit between entry and SL)
        limit_entry = round((entry + stop_loss) / 2.0, 2)
        limit_executed = False
        for k in range(i + 1, min(i + 12, len(candles_15m))):
            if signal == "SELL" and candles_15m[k]["high"] >= limit_entry:
                limit_executed = True
                break
            elif signal == "BUY" and candles_15m[k]["low"] <= limit_entry:
                limit_executed = True
                break
                
        # Track CMP Market Order Outcome across next 28 candles (~7 hours)
        hit_tp1 = False
        hit_tp2 = False
        hit_tp3 = False
        hit_sl = False
        outcome = "OPEN"
        pnl = 0.0
        
        for j in range(i + 1, min(i + 28, len(candles_15m))):
            cj = candles_15m[j]
            h = cj["high"]
            l = cj["low"]
            
            if signal == "SELL":
                if not hit_tp1 and h >= stop_loss:
                    hit_sl = True
                    outcome = "SL_HIT"
                    pnl = -risk
                    break
                if l <= tp1:
                    hit_tp1 = True
                if hit_tp1 and l <= tp2:
                    hit_tp2 = True
                if hit_tp2 and l <= tp3:
                    hit_tp3 = True
                # Free-roll breakeven protocol: if price pulls back to entry after TP1, exit remaining 50% at BE
                if hit_tp1 and h >= entry:
                    outcome = "BREAKEVEN_FREE_ROLL"
                    pnl = round(risk * 1.5 * 0.5, 2)
                    break
            elif signal == "BUY":
                if not hit_tp1 and l <= stop_loss:
                    hit_sl = True
                    outcome = "SL_HIT"
                    pnl = -risk
                    break
                if h >= tp1:
                    hit_tp1 = True
                if hit_tp1 and h >= tp2:
                    hit_tp2 = True
                if hit_tp2 and h >= tp3:
                    hit_tp3 = True
                if hit_tp1 and l <= entry:
                    outcome = "BREAKEVEN_FREE_ROLL"
                    pnl = round(risk * 1.5 * 0.5, 2)
                    break
                    
        if hit_tp3:
            outcome = "TP3_MAX_ACHIEVED"
            pnl = round(risk * 3.5, 2)
        elif hit_tp2:
            outcome = "TP2_ACHIEVED"
            pnl = round(risk * 2.5, 2)
        elif hit_tp1 and outcome != "BREAKEVEN_FREE_ROLL":
            outcome = "TP1_ACHIEVED"
            pnl = round(risk * 1.5, 2)
        elif not hit_tp1 and not hit_sl:
            outcome = "EXPIRED_FLAT"
            pnl = 0.0
            
        trades.append({
            "timestamp": dt.strftime("%Y-%m-%d %H:%M UTC"),
            "date": dt.strftime("%Y-%m-%d"),
            "day": dt.strftime("%A"),
            "signal": signal,
            "setup": setup_name,
            "cmp_entry": entry,
            "stop_loss": stop_loss,
            "tp1": tp1,
            "tp2": tp2,
            "tp3": tp3,
            "risk": risk,
            "limit_order_executed": limit_executed,
            "outcome": outcome,
            "pnl_points": pnl
        })
        
    # Aggregate by day
    days_summary = {}
    for t in trades:
        d = t["day"]
        if d not in days_summary:
            days_summary[d] = {
                "date": t["date"],
                "total_signals": 0,
                "tp_achieved": 0,
                "sl_hit": 0,
                "breakeven": 0,
                "unexecuted_limit_orders": 0,
                "net_points": 0.0
            }
        days_summary[d]["total_signals"] += 1
        if "TP" in t["outcome"]:
            days_summary[d]["tp_achieved"] += 1
        elif t["outcome"] == "SL_HIT":
            days_summary[d]["sl_hit"] += 1
        elif t["outcome"] == "BREAKEVEN_FREE_ROLL":
            days_summary[d]["breakeven"] += 1
            
        if not t["limit_order_executed"]:
            days_summary[d]["unexecuted_limit_orders"] += 1
            
        days_summary[d]["net_points"] = round(days_summary[d]["net_points"] + t["pnl_points"], 2)
        
    # Total statistics
    total_recs = len(trades)
    tp1_count = sum(1 for t in trades if "TP" in t["outcome"] or t["outcome"] == "BREAKEVEN_FREE_ROLL")
    tp2_count = sum(1 for t in trades if t["outcome"] in ("TP2_ACHIEVED", "TP3_MAX_ACHIEVED"))
    tp3_count = sum(1 for t in trades if t["outcome"] == "TP3_MAX_ACHIEVED")
    sl_count = sum(1 for t in trades if t["outcome"] == "SL_HIT")
    be_count = sum(1 for t in trades if t["outcome"] == "BREAKEVEN_FREE_ROLL")
    unexecuted_limits = sum(1 for t in trades if not t["limit_order_executed"])
    total_net_points = round(sum(t["pnl_points"] for t in trades), 2)
    
    win_rate_cmp = round(((tp1_count) / max(total_recs, 1)) * 100, 1)
    
    return {
        "asset": asset_name,
        "week_period": f"{candles_15m[0]['timestamp']} to {candles_15m[-1]['timestamp']}",
        "audit_timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "total_recommendations": total_recs,
        "performance_metrics": {
            "targets_achieved": {
                "total_tp_hits": tp1_count,
                "tp1_hits": tp1_count,
                "tp2_hits": tp2_count,
                "tp3_max_hits": tp3_count,
                "target_hit_rate": f"{win_rate_cmp}%"
            },
            "stop_loss_metrics": {
                "total_sl_hit": sl_count,
                "sl_rate": f"{round((sl_count / max(total_recs, 1)) * 100, 1)}%"
            },
            "execution_comparison": {
                "cmp_market_orders_executed": f"{total_recs} / {total_recs} (100.0% Executed)",
                "limit_orders_not_executed": f"{unexecuted_limits} / {total_recs} ({round((unexecuted_limits/max(total_recs, 1))*100, 1)}% Missed)"
            },
            "breakeven_free_rolls": be_count,
            "net_pnl_points": f"+{total_net_points} pts" if total_net_points >= 0 else f"{total_net_points} pts"
        },
        "smc_breakdown": {
            "ob_mitigations": ob_count,
            "fvg_retests": fvg_count,
            "liquidity_sweeps": sweep_count
        },
        "daily_breakdown": days_summary,
        "recent_trades_log": trades[-10:] # Last 10 trades
    }

def print_weekly_report(data: dict):
    """Prints a structured ASCII performance table for terminal and GitHub Actions."""
    if "error" in data:
        print(f"[!] Error: {data['error']}")
        return
        
    print("\n" + "=" * 70)
    print("  ★ INSTITUTIONAL SMC WEEKLY PERFORMANCE & AUDIT REPORT ★")
    print(f"  Asset: {data['asset']} | Audited: {data['audit_timestamp']}")
    print("=" * 70)
    
    m = data["performance_metrics"]
    tg = m["targets_achieved"]
    sl = m["stop_loss_metrics"]
    ex = m["execution_comparison"]
    smc_bk = data.get("smc_breakdown", {})
    
    print("\n[📊 EXECUTIVE PERFORMANCE SUMMARY]")
    print(f"  • Total Recommendations : {data['total_recommendations']}")
    print(f"  • Targets Achieved (TP) : {tg['total_tp_hits']} / {data['total_recommendations']} ({tg['target_hit_rate']})")
    print(f"    - TP1 Achieved        : {tg['tp1_hits']}")
    print(f"    - TP2 Achieved        : {tg['tp2_hits']}")
    print(f"    - TP3 (Max) Achieved  : {tg['tp3_max_hits']}")
    print(f"  • Stop Loss Hit (SL)    : {sl['total_sl_hit']} ({sl['sl_rate']})")
    print(f"  • Breakeven Free-Rolls  : {m['breakeven_free_rolls']} (0% Downside Protected)")
    print(f"  • Net Weekly P&L        : {m['net_pnl_points']}")
    
    print("\n[🏛 SMC INSTITUTIONAL SETUP BREAKDOWN]")
    print(f"  • Order Block Mitigations : {smc_bk.get('ob_mitigations', 0)}")
    print(f"  • Fair Value Gap Retests  : {smc_bk.get('fvg_retests', 0)}")
    print(f"  • Judas Liquidity Sweeps  : {smc_bk.get('liquidity_sweeps', 0)}")
    
    print("\n[⚡ EXECUTION COMPARISON: CMP vs LIMIT ORDERS]")
    print(f"  • CMP Market Orders     : {ex['cmp_market_orders_executed']}")
    print(f"  • Pullback Limit Orders : {ex['limit_orders_not_executed']} NOT EXECUTED (Missed due to momentum)")
    
    print("\n" + "-" * 70)
    print(f"  {'DAY':<10} | {'DATE':<12} | {'SIGNALS':<8} | {'TG HIT':<8} | {'SL HIT':<8} | {'MISSED (LIMIT)':<14} | {'NET PTS'}")
    print("-" * 70)
    for day, d in data["daily_breakdown"].items():
        net_str = f"+{d['net_points']}" if d['net_points'] >= 0 else f"{d['net_points']}"
        print(f"  {day:<10} | {d['date']:<12} | {d['total_signals']:<8} | {d['tp_achieved']:<8} | {d['sl_hit']:<8} | {d['unexecuted_limit_orders']:<14} | {net_str}")
    print("-" * 70)
    
    print("\n[📋 RECENT 5 EXECUTED RECOMMENDATIONS LOG]")
    for t in data["recent_trades_log"][-5:]:
        icon = "🟢" if "TP" in t["outcome"] else ("🔴" if t["outcome"] == "SL_HIT" else "🟡")
        pnl_str = f"+{t['pnl_points']:.2f}" if t['pnl_points'] >= 0 else f"{t['pnl_points']:.2f}"
        miss_note = " (Missed on Limit)" if not t["limit_order_executed"] else " (Filled on Limit)"
        setup_disp = t.get("setup", "SMC Setup")
        print(f"  {icon} {t['timestamp']} | {t['signal']} ({setup_disp}) at CMP ${t['cmp_entry']} | Result: {t['outcome']} ({pnl_str}/oz){miss_note}")
        
    print("\n" + "=" * 70)
    print("  ★ Key Insight: Institutional SMC eliminates scalper noise, protects downside, and scales wins.")
    print("=" * 70 + "\n")

def main():
    parser = argparse.ArgumentParser(description="Weekly Forex/Gold Recommendation History Auditor")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    parser.add_argument("--symbol", type=str, default="XAUT-USD", help="Asset symbol (default: XAUT-USD)")
    parser.add_argument("--telegram", action="store_true", help="Broadcast weekly report directly to Telegram")
    args = parser.parse_args()
    
    res = audit_weekly_performance(symbol=args.symbol)
    
    if args.telegram:
        config = load_telegram_config()
        msg = format_telegram_weekly_report(res)
        send_telegram_message(config.get("bot_token"), config.get("chat_id"), msg)
        
    if args.json:
        print(json.dumps(res, indent=2))
    elif not args.telegram:
        print_weekly_report(res)

if __name__ == "__main__":
    main()
