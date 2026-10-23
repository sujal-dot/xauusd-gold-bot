#!/usr/bin/env python3
"""
Forex Gold (XAU/USD) Multi-Timeframe Signal & Confluence Engine
Fetches live market data for Gold (GC=F / XAUUSD) and US Dollar Index (DX-Y.NYB),
calculates technical indicators (EMA, RSI, MACD, ATR, Pivots, SMC Order Blocks/FVG),
and produces institutional-grade trading signals with exact Entry, SL, and TP levels.
"""

import sys
import json
import argparse
import urllib.request
import urllib.error
from datetime import datetime

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def fetch_candles(symbol: str, interval: str = "1h", range_val: str = "5d"):
    """Fetches historical OHLCV candle data from Yahoo Finance API."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval={interval}&range={range_val}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            data = json.loads(response.read().decode("utf-8"))
            result = data["chart"]["result"][0]
            timestamps = result.get("timestamp", [])
            quotes = result["indicators"]["quote"][0]
            
            candles = []
            for i in range(len(timestamps)):
                c = quotes["close"][i]
                o = quotes["open"][i]
                h = quotes["high"][i]
                l = quotes["low"][i]
                v = quotes["volume"][i] or 0
                if None not in (c, o, h, l):
                    candles.append({
                        "timestamp": timestamps[i],
                        "open": float(o),
                        "high": float(h),
                        "low": float(l),
                        "close": float(c),
                        "volume": float(v)
                    })
            return candles
    except Exception as e:
        return []

def calculate_ema(prices, period):
    """Calculates Exponential Moving Average (EMA)."""
    if len(prices) < period:
        return [prices[-1]] * len(prices) if prices else []
    multiplier = 2 / (period + 1)
    ema = [sum(prices[:period]) / period]
    for price in prices[period:]:
        ema.append((price - ema[-1]) * multiplier + ema[-1])
    # Pad beginning
    return [ema[0]] * (period - 1) + ema

def calculate_rsi(prices, period=14):
    """Calculates Relative Strength Index (RSI) using Wilder's smoothing."""
    if len(prices) <= period:
        return 50.0
    gains = []
    losses = []
    for i in range(1, len(prices)):
        delta = prices[i] - prices[i - 1]
        gains.append(max(delta, 0))
        losses.append(max(-delta, 0))
    
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))

def calculate_atr(candles, period=14):
    """Calculates Average True Range (ATR)."""
    if len(candles) < 2:
        return 5.0
    true_ranges = []
    for i in range(1, len(candles)):
        h = candles[i]["high"]
        l = candles[i]["low"]
        prev_c = candles[i - 1]["close"]
        tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
        true_ranges.append(tr)
    
    if len(true_ranges) < period:
        return sum(true_ranges) / len(true_ranges) if true_ranges else 5.0
    
    atr = sum(true_ranges[:period]) / period
    for i in range(period, len(true_ranges)):
        atr = (atr * (period - 1) + true_ranges[i]) / period
    return atr

def calculate_macd(prices):
    """Calculates MACD (12, 26, 9)."""
    if len(prices) < 35:
        return 0, 0, 0
    ema12 = calculate_ema(prices, 12)
    ema26 = calculate_ema(prices, 26)
    macd_line = [fast - slow for fast, slow in zip(ema12, ema26)]
    signal_line = calculate_ema(macd_line[25:], 9)
    # Align lengths
    curr_macd = macd_line[-1]
    curr_signal = signal_line[-1] if signal_line else 0
    hist = curr_macd - curr_signal
    return curr_macd, curr_signal, hist

def find_swings_and_fvg(candles):
    """Identifies recent Swing Highs, Swing Lows, and Fair Value Gaps (FVG)."""
    if len(candles) < 10:
        return None, None, []
    
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    
    recent_high = max(highs[-20:])
    recent_low = min(lows[-20:])
    
    # Detect FVG in last 10 candles
    fvgs = []
    for i in range(len(candles) - 10, len(candles) - 1):
        if i >= 2:
            # Bullish FVG: Candle i-2 High < Candle i Low
            if candles[i]["low"] > candles[i - 2]["high"]:
                fvgs.append({
                    "type": "BULLISH_FVG",
                    "top": round(candles[i]["low"], 2),
                    "bottom": round(candles[i - 2]["high"], 2),
                    "mid": round((candles[i]["low"] + candles[i - 2]["high"]) / 2, 2)
                })
            # Bearish FVG: Candle i-2 Low > Candle i High
            elif candles[i - 2]["low"] > candles[i]["high"]:
                fvgs.append({
                    "type": "BEARISH_FVG",
                    "top": round(candles[i - 2]["low"], 2),
                    "bottom": round(candles[i]["high"], 2),
                    "mid": round((candles[i - 2]["low"] + candles[i]["high"]) / 2, 2)
                })
    return recent_high, recent_low, fvgs

def calculate_pivot_points(candles_daily):
    """Calculates Classic and Fibonacci Pivot Points from yesterday's daily candle."""
    if len(candles_daily) < 2:
        return {}
    prev = candles_daily[-2]  # Completed previous day
    high = prev["high"]
    low = prev["low"]
    close = prev["close"]
    
    pp = (high + low + close) / 3.0
    r1 = (2 * pp) - low
    s1 = (2 * pp) - high
    r2 = pp + (high - low)
    s2 = pp - (high - low)
    r3 = high + 2 * (pp - low)
    s3 = low - 2 * (high - pp)
    
    # Fibonacci Pivots
    diff = high - low
    fib_r1 = pp + 0.382 * diff
    fib_r2 = pp + 0.618 * diff
    fib_r3 = pp + 1.000 * diff
    fib_s1 = pp - 0.382 * diff
    fib_s2 = pp - 0.618 * diff
    fib_s3 = pp - 1.000 * diff
    
    return {
        "classic": {
            "R3": round(r3, 2), "R2": round(r2, 2), "R1": round(r1, 2),
            "PP": round(pp, 2),
            "S1": round(s1, 2), "S2": round(s2, 2), "S3": round(s3, 2)
        },
        "fibonacci": {
            "R3": round(fib_r3, 2), "R2": round(fib_r2, 2), "R1": round(fib_r1, 2),
            "PP": round(pp, 2),
            "S1": round(fib_s1, 2), "S2": round(fib_s2, 2), "S3": round(fib_s3, 2)
        }
    }

def analyze_gold_scalp():
    """
    Dedicated high-frequency scalping engine for Gold (XAU/USD).
    Focuses on 5M execution, 15M structure, 5M EMAs (9, 21, 50), tight ATR stops ($2.50-$4.50),
    Fair Value Gaps (FVG), micro liquidity sweeps, and fast DXY 15M correlation.
    """
    gold_5m = fetch_candles("GC=F", interval="5m", range_val="2d")
    gold_15m = fetch_candles("GC=F", interval="15m", range_val="5d")
    gold_daily = fetch_candles("GC=F", interval="1d", range_val="6mo")
    dxy_15m = fetch_candles("DX-Y.NYB", interval="15m", range_val="5d")
    
    if not gold_5m or not gold_15m:
        return {"error": "Unable to fetch 5M/15M Gold market data from provider. Verify internet connection."}
        
    current_price = gold_5m[-1]["close"]
    prices_5m = [c["close"] for c in gold_5m]
    prices_15m = [c["close"] for c in gold_15m]
    
    # 5M Indicators (Execution)
    ema9_5m = calculate_ema(prices_5m, 9)[-1]
    ema21_5m = calculate_ema(prices_5m, 21)[-1]
    ema50_5m = calculate_ema(prices_5m, 50)[-1]
    rsi_5m = calculate_rsi(prices_5m, 14)
    atr_5m = calculate_atr(gold_5m, 14)
    macd_line_5m, macd_sig_5m, macd_hist_5m = calculate_macd(prices_5m)
    swing_high_5m, swing_low_5m, fvgs_5m = find_swings_and_fvg(gold_5m)
    
    # 15M Indicators (Trend Context)
    ema20_15m = calculate_ema(prices_15m, 20)[-1]
    ema50_15m = calculate_ema(prices_15m, 50)[-1]
    rsi_15m = calculate_rsi(prices_15m, 14)
    
    # Pivots
    pivots = calculate_pivot_points(gold_daily) if gold_daily else {}
    
    # DXY 15M Intermarket Correlation
    dxy_trend = "NEUTRAL"
    dxy_price = None
    if dxy_15m and len(dxy_15m) >= 20:
        dxy_prices = [c["close"] for c in dxy_15m]
        dxy_price = dxy_prices[-1]
        dxy_ema20 = calculate_ema(dxy_prices, 20)[-1]
        if dxy_price > dxy_ema20 and dxy_prices[-1] > dxy_prices[-5]:
            dxy_trend = "BULLISH (Headwind for Gold)"
        elif dxy_price < dxy_ema20 and dxy_prices[-1] < dxy_prices[-5]:
            dxy_trend = "BEARISH (Tailwind for Gold)"
            
    bullish_factors = []
    bearish_factors = []
    
    # Trend & EMA Alignment
    if current_price > ema9_5m > ema21_5m:
        bullish_factors.append(f"5M Bullish EMA stack (Price > 9 EMA {ema9_5m:.2f} > 21 EMA {ema21_5m:.2f})")
    elif current_price < ema9_5m < ema21_5m:
        bearish_factors.append(f"5M Bearish EMA stack (Price < 9 EMA {ema9_5m:.2f} < 21 EMA {ema21_5m:.2f})")
        
    if current_price > ema50_5m:
        bullish_factors.append(f"5M Price above 50 EMA baseline resistance ({ema50_5m:.2f})")
    else:
        bearish_factors.append(f"5M Price capped below 50 EMA baseline resistance ({ema50_5m:.2f})")
        
    if current_price > ema20_15m:
        bullish_factors.append(f"15M Trend alignment bullish (Price above 20 EMA {ema20_15m:.2f})")
    else:
        bearish_factors.append(f"15M Trend alignment bearish (Price below 20 EMA {ema20_15m:.2f})")
        
    # RSI Momentum
    if 50 <= rsi_5m <= 65:
        bullish_factors.append(f"5M RSI bullish expansion ({rsi_5m:.1f})")
    elif rsi_5m > 70:
        bearish_factors.append(f"5M RSI Overbought ({rsi_5m:.1f}) - scalp pullback expected")
    elif 35 <= rsi_5m < 50:
        bearish_factors.append(f"5M RSI bearish continuation momentum ({rsi_5m:.1f})")
    elif rsi_5m < 30:
        bullish_factors.append(f"5M RSI Oversold ({rsi_5m:.1f}) - short exhaustion / mean reversion bounce")
        
    # MACD Momentum
    if macd_hist_5m > 0:
        bullish_factors.append("5M MACD Histogram positive with buyer momentum")
    else:
        bearish_factors.append("5M MACD Histogram negative with seller momentum")
        
    # DXY Confluence
    if "Tailwind" in dxy_trend:
        bullish_factors.append(f"DXY 15M falling ({dxy_price:.2f}) - inverse tailwind for Gold scalp")
    elif "Headwind" in dxy_trend:
        bearish_factors.append(f"DXY 15M strengthening ({dxy_price:.2f}) - headwind pressure for Gold scalp")
        
    # Pivots
    pp = pivots.get("classic", {}).get("PP", current_price)
    if current_price > pp:
        bullish_factors.append(f"Trading above Daily Pivot ({pp:.2f})")
    else:
        bearish_factors.append(f"Trading below Daily Pivot ({pp:.2f})")
        
    bull_score = len(bullish_factors)
    bear_score = len(bearish_factors)
    total = max(bull_score + bear_score, 1)
    
    # Scalp ATR-based Stop & Target buffers
    sl_buffer = max(min(round(atr_5m * 1.35, 2), 4.50), 2.50)
    
    if bear_score >= bull_score + 1:
        bias = "BEARISH"
        confidence = min(round((bear_score / total) * 100), 90)
        
        # In scalping, if RSI < 32 and 9 EMA is above price, sell the pullback retest
        if rsi_5m < 32 and ema9_5m > current_price:
            signal_type = "SCALP SELL (WAIT PULLBACK TO 9/21 EMA)"
            entry_low = round(min(ema9_5m, ema21_5m), 2)
            entry_high = round(max(ema9_5m, ema21_5m), 2)
            ideal_entry = round((entry_low + entry_high) / 2, 2)
            stop_loss = round(entry_high + sl_buffer, 2)
        else:
            signal_type = "SCALP SELL"
            entry_low = round(current_price, 2)
            entry_high = round(max(current_price + (atr_5m * 0.4), ema9_5m), 2)
            ideal_entry = round(current_price, 2)
            stop_loss = round(entry_high + sl_buffer, 2)
            
        risk = round(abs(stop_loss - ideal_entry), 2)
        tp1 = round(ideal_entry - (risk * 1.5), 2)
        tp2 = round(ideal_entry - (risk * 2.5), 2)
        tp3 = round(ideal_entry - (risk * 3.5), 2)
        
    elif bull_score >= bear_score + 1:
        bias = "BULLISH"
        confidence = min(round((bull_score / total) * 100), 90)
        
        if rsi_5m > 68 and ema9_5m < current_price:
            signal_type = "SCALP BUY (WAIT PULLBACK TO 9/21 EMA)"
            entry_low = round(min(ema9_5m, ema21_5m), 2)
            entry_high = round(max(ema9_5m, ema21_5m), 2)
            ideal_entry = round((entry_low + entry_high) / 2, 2)
            stop_loss = round(entry_low - sl_buffer, 2)
        else:
            signal_type = "SCALP BUY"
            entry_low = round(min(current_price - (atr_5m * 0.4), ema9_5m), 2)
            entry_high = round(current_price, 2)
            ideal_entry = round(current_price, 2)
            stop_loss = round(entry_low - sl_buffer, 2)
            
        risk = round(abs(ideal_entry - stop_loss), 2)
        tp1 = round(ideal_entry + (risk * 1.5), 2)
        tp2 = round(ideal_entry + (risk * 2.5), 2)
        tp3 = round(ideal_entry + (risk * 3.5), 2)
        
    else:
        signal_type = "SCALP RANGE (FADE EXTREMES)"
        bias = "CONSOLIDATION"
        confidence = 55
        ideal_entry = round(current_price, 2)
        entry_low = round(current_price - 1.50, 2)
        entry_high = round(current_price + 1.50, 2)
        stop_loss = round(entry_low - 2.50, 2)
        risk = 2.50
        tp1 = round(current_price + 3.75, 2)
        tp2 = round(current_price + 6.25, 2)
        tp3 = round(current_price + 8.75, 2)
        
    return {
        "asset": "XAU/USD (Gold) - Scalp Engine",
        "timeframe": "5M Execution / 15M Trend",
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "current_price": round(current_price, 2),
        "signal": signal_type,
        "bias": bias,
        "confidence_percent": confidence,
        "execution": {
            "entry_range": f"${min(entry_low, entry_high):.2f} – ${max(entry_low, entry_high):.2f}",
            "ideal_entry": f"${ideal_entry:.2f}",
            "stop_loss": f"${stop_loss:.2f}",
            "risk_per_ounce": f"${risk:.2f}",
            "take_profit_1": f"${tp1:.2f} (1:1.5 R:R - Quick Scalp Target)",
            "take_profit_2": f"${tp2:.2f} (1:2.5 R:R - Key Liquidity Sweep / Extended)",
            "take_profit_3": f"${tp3:.2f} (1:3.5 R:R - Session Runner)",
            "trade_management": "Move Stop Loss to Break-Even immediately once TP1 is hit. Close 60% position at TP1, let 40% run to TP2/TP3. Average hold time: 5–30 mins."
        },
        "indicators": {
            "atr_14_5m": round(atr_5m, 2),
            "rsi_14_5m": round(rsi_5m, 1),
            "rsi_14_15m": round(rsi_15m, 1),
            "ema_9_5m": round(ema9_5m, 2),
            "ema_21_5m": round(ema21_5m, 2),
            "ema_50_5m": round(ema50_5m, 2),
            "ema_20_15m": round(ema20_15m, 2),
            "ema_50_15m": round(ema50_15m, 2),
            "macd_hist_5m": round(macd_hist_5m, 3),
            "dxy_trend": dxy_trend,
            "dxy_price": round(dxy_price, 2) if dxy_price else "N/A"
        },
        "pivots_daily": pivots.get("classic", {}),
        "fvgs_detected": fvgs_5m[:3],
        "confluence_reasons": {
            "bullish": bullish_factors,
            "bearish": bearish_factors
        }
    }

def analyze_gold(timeframe_mode="scalp"):
    """
    Main signal generation function.
    Supports 'scalp', 'intraday', and 'swing' modes.
    """
    if timeframe_mode == "scalp":
        return analyze_gold_scalp()
        
    # 1. Fetch data
    gold_15m = fetch_candles("GC=F", interval="15m", range_val="5d")
    gold_1h = fetch_candles("GC=F", interval="1h", range_val="1mo")
    gold_daily = fetch_candles("GC=F", interval="1d", range_val="6mo")
    dxy_1h = fetch_candles("DX-Y.NYB", interval="1h", range_val="5d")
    
    if not gold_1h or not gold_daily:
        return {"error": "Unable to fetch Gold market data from provider. Verify internet connection."}
    
    current_price = gold_1h[-1]["close"]
    prices_1h = [c["close"] for c in gold_1h]
    prices_daily = [c["close"] for c in gold_daily]
    
    # 2. Indicators on 1H (Execution & Tactical)
    ema20_1h = calculate_ema(prices_1h, 20)[-1]
    ema50_1h = calculate_ema(prices_1h, 50)[-1]
    ema200_1h = calculate_ema(prices_1h, 200)[-1]
    rsi_1h = calculate_rsi(prices_1h, 14)
    atr_1h = calculate_atr(gold_1h, 14)
    macd_line, macd_sig, macd_hist = calculate_macd(prices_1h)
    
    # 3. Indicators on Daily (Macro Trend)
    ema50_d = calculate_ema(prices_daily, 50)[-1]
    ema200_d = calculate_ema(prices_daily, 200)[-1]
    rsi_daily = calculate_rsi(prices_daily, 14)
    
    # 4. Swings, FVG and Pivots
    swing_high, swing_low, fvgs = find_swings_and_fvg(gold_1h)
    pivots = calculate_pivot_points(gold_daily)
    
    # 5. DXY Intermarket Correlation
    dxy_trend = "NEUTRAL"
    dxy_price = None
    if dxy_1h and len(dxy_1h) >= 20:
        dxy_prices = [c["close"] for c in dxy_1h]
        dxy_price = dxy_prices[-1]
        dxy_ema20 = calculate_ema(dxy_prices, 20)[-1]
        if dxy_price > dxy_ema20 and dxy_prices[-1] > dxy_prices[-5]:
            dxy_trend = "BULLISH (Headwind for Gold)"
        elif dxy_price < dxy_ema20 and dxy_prices[-1] < dxy_prices[-5]:
            dxy_trend = "BEARISH (Tailwind for Gold)"
    
    # 6. Scoring & Confluence Evaluation
    bullish_factors = []
    bearish_factors = []
    
    # Daily trend
    if current_price > ema50_d > ema200_d:
        bullish_factors.append("Daily Macro Trend is Bullish (Price > 50 EMA > 200 EMA)")
    elif current_price < ema50_d < ema200_d:
        bearish_factors.append("Daily Macro Trend is Bearish (Price < 50 EMA < 200 EMA)")
    
    # 1H trend alignment
    if current_price > ema50_1h:
        bullish_factors.append(f"1H Price ({current_price:.2f}) trading above 50 EMA ({ema50_1h:.2f})")
    else:
        bearish_factors.append(f"1H Price ({current_price:.2f}) trading below 50 EMA ({ema50_1h:.2f})")
        
    if current_price > ema200_1h:
        bullish_factors.append(f"1H Price above key 200 EMA support ({ema200_1h:.2f})")
    else:
        bearish_factors.append(f"1H Price capped below key 200 EMA resistance ({ema200_1h:.2f})")
    
    # RSI Momentum
    if 50 <= rsi_1h <= 68:
        bullish_factors.append(f"1H RSI healthy bullish momentum ({rsi_1h:.1f})")
    elif rsi_1h > 70:
        bearish_factors.append(f"1H RSI Overbought ({rsi_1h:.1f}) - beware of pullback/exhaustion")
    elif 32 <= rsi_1h < 50:
        bearish_factors.append(f"1H RSI bearish momentum ({rsi_1h:.1f})")
    elif rsi_1h < 30:
        bullish_factors.append(f"1H RSI Oversold ({rsi_1h:.1f}) - potential mean reversion/bounce")
        
    # MACD
    if macd_hist > 0 and macd_line > macd_sig:
        bullish_factors.append("1H MACD Histogram positive with bullish crossover")
    elif macd_hist < 0 and macd_line < macd_sig:
        bearish_factors.append("1H MACD Histogram negative with bearish cross")
        
    # Pivots
    pp = pivots.get("classic", {}).get("PP", current_price)
    if current_price > pp:
        bullish_factors.append(f"Trading above Daily Pivot Point ({pp:.2f})")
    else:
        bearish_factors.append(f"Trading below Daily Pivot Point ({pp:.2f})")
        
    # DXY Influence
    if "Tailwind" in dxy_trend:
        bullish_factors.append(f"DXY Index falling ({dxy_price:.2f}) - classic inverse boost for Gold")
    elif "Headwind" in dxy_trend:
        bearish_factors.append(f"DXY Index strengthening ({dxy_price:.2f}) - putting pressure on Gold")

    # 7. Determine Signal & Trade Parameters
    bull_score = len(bullish_factors)
    bear_score = len(bearish_factors)
    total_confluences = bull_score + bear_score
    
    # Minimum ATR buffer for Gold (standard XAUUSD moves fast)
    sl_atr_mult = 1.6
    tp1_atr_mult = 2.4   # 1:1.5 RR
    tp2_atr_mult = 4.0   # 1:2.5 RR
    tp3_atr_mult = 5.6   # 1:3.5 RR
    
    sl_distance = max(atr_1h * sl_atr_mult, 8.0) # at least $8 buffer on gold
    
    if bull_score >= bear_score + 2:
        signal_type = "STRONG BUY" if bull_score >= 5 else "BUY (PULLBACK / DIP)"
        bias = "BULLISH"
        confidence = min(round((bull_score / max(total_confluences, 1)) * 100), 92)
        
        # Pullback entry zone around EMA20 or current price
        entry_ideal = current_price
        entry_low = round(min(current_price - (atr_1h * 0.4), ema20_1h), 2)
        entry_high = round(current_price, 2)
        
        stop_loss = round(entry_low - sl_distance, 2)
        # Check swing low for structural protection
        if swing_low and swing_low < current_price and abs(current_price - swing_low) < (sl_distance * 1.5):
            stop_loss = round(swing_low - 2.5, 2)
            
        risk = entry_ideal - stop_loss
        tp1 = round(entry_ideal + (risk * 1.5), 2)
        tp2 = round(entry_ideal + (risk * 2.5), 2)
        tp3 = round(entry_ideal + (risk * 3.5), 2)
        
    elif bear_score >= bull_score + 2:
        signal_type = "STRONG SELL" if bear_score >= 5 else "SELL (RALLY / RETEST)"
        bias = "BEARISH"
        confidence = min(round((bear_score / max(total_confluences, 1)) * 100), 92)
        
        entry_ideal = current_price
        entry_high = round(max(current_price + (atr_1h * 0.4), ema20_1h), 2)
        entry_low = round(current_price, 2)
        
        stop_loss = round(entry_high + sl_distance, 2)
        if swing_high and swing_high > current_price and abs(swing_high - current_price) < (sl_distance * 1.5):
            stop_loss = round(swing_high + 2.5, 2)
            
        risk = stop_loss - entry_ideal
        tp1 = round(entry_ideal - (risk * 1.5), 2)
        tp2 = round(entry_ideal - (risk * 2.5), 2)
        tp3 = round(entry_ideal - (risk * 3.5), 2)
        
    else:
        signal_type = "NEUTRAL / RANGE-BOUND"
        bias = "CONSOLIDATION"
        confidence = 50
        entry_low = round(pivots.get("classic", {}).get("S1", current_price - 10), 2)
        entry_high = round(pivots.get("classic", {}).get("R1", current_price + 10), 2)
        stop_loss = round(entry_low - sl_distance, 2)
        risk = 10.0
        tp1 = round(current_price + 10.0, 2)
        tp2 = round(current_price + 20.0, 2)
        tp3 = round(current_price + 30.0, 2)

    return {
        "asset": "XAU/USD (Gold)",
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "current_price": round(current_price, 2),
        "signal": signal_type,
        "bias": bias,
        "confidence_percent": confidence,
        "execution": {
            "entry_range": f"${min(entry_low, entry_high):.2f} – ${max(entry_low, entry_high):.2f}",
            "ideal_entry": f"${current_price:.2f}",
            "stop_loss": f"${stop_loss:.2f}",
            "risk_per_ounce": f"${abs(current_price - stop_loss):.2f}",
            "take_profit_1": f"${tp1:.2f} (1:1.5 R:R)",
            "take_profit_2": f"${tp2:.2f} (1:2.5 R:R)",
            "take_profit_3": f"${tp3:.2f} (Runner / Structure Target)",
            "trade_management": "Move Stop Loss to Break-Even when TP1 is hit. Take 50% partial profit at TP1."
        },
        "indicators": {
            "atr_14_1h": round(atr_1h, 2),
            "rsi_14_1h": round(rsi_1h, 1),
            "rsi_14_daily": round(rsi_daily, 1),
            "ema_20_1h": round(ema20_1h, 2),
            "ema_50_1h": round(ema50_1h, 2),
            "ema_200_1h": round(ema200_1h, 2),
            "ema_50_daily": round(ema50_d, 2),
            "ema_200_daily": round(ema200_d, 2),
            "macd_hist_1h": round(macd_hist, 3),
            "dxy_trend": dxy_trend,
            "dxy_price": round(dxy_price, 2) if dxy_price else "N/A"
        },
        "pivots_daily": pivots.get("classic", {}),
        "fvgs_detected": fvgs[:3],
        "confluence_reasons": {
            "bullish": bullish_factors,
            "bearish": bearish_factors
        }
    }

def print_terminal_report(res):
    """Outputs a clean, institutional report for the terminal/chat."""
    if "error" in res:
        print(f"[!] Error: {res['error']}")
        return
        
    print("\n" + "=" * 65)
    print(f"  ★ FOREX GOLD (XAU/USD) INSTITUTIONAL SIGNAL & ANALYSIS ★")
    print(f"  Generated: {res['timestamp']} | Current Price: ${res['current_price']:.2f}")
    print("=" * 65)
    
    sig = res['signal']
    color_prefix = "🟢" if "BUY" in sig else ("🔴" if "SELL" in sig else "🟡")
    print(f"\n{color_prefix} SIGNAL: {res['signal']}  |  BIAS: {res['bias']}  |  CONFIDENCE: {res['confidence_percent']}%")
    print("-" * 65)
    
    ex = res['execution']
    print(f"  • Entry Zone   : {ex['entry_range']} (Market: {ex['ideal_entry']})")
    print(f"  • Stop Loss    : {ex['stop_loss']} (Risk: {ex['risk_per_ounce']}/oz)")
    print(f"  • Target 1     : {ex['take_profit_1']}")
    print(f"  • Target 2     : {ex['take_profit_2']}")
    print(f"  • Target 3     : {ex['take_profit_3']}")
    print(f"  • Rules        : {ex['trade_management']}")
    
    print("\n[📊 KEY TECHNICALS & MACRO CONFLUENCE]")
    ind = res['indicators']
    if 'atr_14_5m' in ind:
        print(f"  • Execution Mode : Scalp (5M Execution / 15M Trend Structure)")
        print(f"  • 5M RSI: {ind.get('rsi_14_5m')} | 15M RSI: {ind.get('rsi_14_15m')} | 5M ATR: ${ind.get('atr_14_5m')}")
        print(f"  • 5M Fast EMAs: 9 EMA: ${ind.get('ema_9_5m')} | 21 EMA: ${ind.get('ema_21_5m')} | 50 EMA: ${ind.get('ema_50_5m')}")
        print(f"  • 15M Trend EMAs: 20 EMA: ${ind.get('ema_20_15m')} | 50 EMA: ${ind.get('ema_50_15m')}")
        print(f"  • US Dollar Index (DXY): {ind.get('dxy_trend')} ({ind.get('dxy_price')})")
    else:
        print(f"  • 1H RSI: {ind.get('rsi_14_1h')}  | Daily RSI: {ind.get('rsi_14_daily')} | 1H ATR (Volatility): ${ind.get('atr_14_1h')}")
        print(f"  • 1H EMAs: 20 EMA: ${ind.get('ema_20_1h')} | 50 EMA: ${ind.get('ema_50_1h')} | 200 EMA: ${ind.get('ema_200_1h')}")
        print(f"  • Daily Trend EMAs: 50 EMA: ${ind.get('ema_50_daily')} | 200 EMA: ${ind.get('ema_200_daily')}")
        print(f"  • US Dollar Index (DXY): {ind.get('dxy_trend')} ({ind.get('dxy_price')})")
    
    print("\n[🎯 DAILY PIVOT LEVELS (XAU/USD)]")
    p = res['pivots_daily']
    print(f"  Resistance: R3: ${p.get('R3')} | R2: ${p.get('R2')} | R1: ${p.get('R1')}")
    print(f"  Central PP: ${p.get('PP')}")
    print(f"  Support   : S1: ${p.get('S1')} | S2: ${p.get('S2')} | S3: ${p.get('S3')}")
    
    print("\n[✅ CONFLUENCE BREAKDOWN]")
    print("  Bullish Evidence:")
    for b in res['confluence_reasons']['bullish']:
        print(f"    [+] {b}")
    print("  Bearish Evidence:")
    for b in res['confluence_reasons']['bearish']:
        print(f"    [-] {b}")
        
    if res.get('fvgs_detected'):
        print("\n[⚡ RECENT FAIR VALUE GAPS (FVG)]")
        for f in res['fvgs_detected']:
            print(f"    {f['type']}: Range ${f['bottom']} – ${f['top']} (Mid: ${f['mid']})")
            
    print("\n" + "=" * 65)
    print("  ⚠️ Risk Disclaimer: Gold is highly volatile. Max recommended risk: 1-2% of account equity.")
    print("=" * 65 + "\n")

def main():
    parser = argparse.ArgumentParser(description="Forex Gold (XAU/USD) Signal Generator")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    parser.add_argument("--timeframe", choices=["scalp", "intraday", "swing"], default="scalp", help="Trading style (default: scalp)")
    args = parser.parse_args()
    
    result = analyze_gold(timeframe_mode=args.timeframe)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_terminal_report(result)

if __name__ == "__main__":
    main()
