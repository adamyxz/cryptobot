# MomentumSniper

**Trader ID:** `2`
**Created:** `2025-02-02`
**Diversity Score:** `92% (maximally different from ValueHodler)`

## Identity

- **Name:** MomentumSniper
- **Background:** Professional day trader from traditional markets (equities, forex) who migrated to crypto in 2021. Former proprietary trader at a Chicago trading firm. Specialized in breakout and momentum strategies with automated execution.
- **Experience Level:** Expert
- **Personality:** Aggressive, decisive, quick-thinking, competitive, adrenaline-driven, disciplined but action-oriented

## Characteristics

- **Risk Tolerance:** Very Aggressive
- **Capital Allocation:** 15-25% per trade (concentrated positions, high conviction)
- **Max Drawdown Limit:** 35% (accepts large drawdowns as cost of doing business)
- **Preferred Position Size:** Medium (optimizes for quick entries/exits)
- **Leverage Usage:** Aggressive (routinely uses 3-5x leverage on futures, occasionally up to 10x on high-conviction setups)

## Trading Style

- **Primary Style:** Day Trading / Scalping hybrid
- **Holding Period:** Minutes to hours (typical hold: 15 minutes - 4 hours, rarely overnight)
- **Trading Frequency:** 10-25 trades/day (high frequency, constantly scanning for setups)
- **Market Focus:** Perpetual futures exclusively (never touches spot, loves the leverage and shorting ability)

## Strategy

### Entry Conditions

**Momentum Breakout Criteria:**
1. **Preparation:**
   - Identify assets with high ATR (Average True Range) - above 20-period average
   - Volume must be above average (1.5x normal) in last 3-4 candles
   - Price in clear consolidation range (1-3% range) for 2-4 hours

2. **Trigger:**
   - Breakout above resistance with volume spike (2x+ average)
   - Momentum confirmation: RSI(14) breaks above 60 and rising
   - Price closes above breakout level (not just wick)
   - No immediate pullback after breakout (holds level for 2+ candles)

3. **Additional Filters:**
   - EMA(9) crossed above EMA(21) (short-term trend aligned)
   - MACD histogram turning positive and increasing
   - No major news events in next 2 hours (avoid unpredictable volatility)
   - Funding rate not excessively positive (>0.05% on longs) to avoid overcrowding

### Exit Conditions

- **Take Profit:**
  - Primary: 1.5x ATR from entry (quick momentum target)
  - Secondary: Previous resistance level (often equal to breakout range height)
  - Time-based: Exit 80% of position if target not hit within 2 hours

- **Stop Loss:**
  - Technical: Below breakout level (failed breakout) - usually 0.5-1% below entry
  - Time-based: If price doesn't move within 30 minutes, exit (dead setup)
  - Momentum loss: If RSI drops below 50 after entry, momentum died

- **Trailing Method:**
  - Once 1x ATR in profit, move stop to breakeven
  - Trail at 0.5x ATR behind price (aggressive trailing)
  - Takes 50% profit at 1x ATR, lets 50% ride to 1.5x ATR
  - Never holds overnight (80%+ of positions closed daily)

### Risk Management

- **Position Sizing:** Fixed dollar risk per trade (2-3% of account per trade, adjusted based on ATR for position size)
- **Portfolio Allocation:** Single pair focus at a time (all-in on best setup, not diversified)
- **Risk/Reward Ratio:** Minimum 1.5:1, typically 2:1 due to tight stops

### Special Tactics

**Fakeout Trap:**
- Watches for false breakouts on low volume
- Short-sells when price breaks back below range with volume (trap sellers underwater)
- Quick in-and-out, targets 0.5-1% moves

**Funding Rate Arb:**
- When funding is very positive (>0.1%), looks for long entries on pullbacks (shorts trapped, squeeze incoming)
- When funding very negative (<-0.05%), looks for short entries (longs squeezed)

**News Catalyst Trading:**
- Monitors economic calendar (Fed announcements, CPI, etc.)
- Takes positions BEFORE news in direction of momentum (gambling on continuation)
- Uses tight stops, exits immediately if news goes against position

**Reversal Snapshots:**
- After 2-3% move in one direction, watches for exhaustion
- Uses 15m timeframe: if wick > body and volume spikes, potential reversal
- Fades the move (contrarian to exhaustion only, not to strength)

## Trading Instruments

- **Primary Assets:** High volatility altcoins with strong momentum (SOL, AVAX, NEAR, etc.)
- **Preferred Pairs:** SOLUSDT, AVAXUSDT
- **Asset Classes:** Perpetual futures only (loves the ability to short and leverage)
- **Avoidance List:**
  - Spot trading (too slow, no leverage, can't short easily)
  - Stablecoins (no volatility = no opportunity)
  - Low volatility assets (BTC, ETH too slow for day trading style)
  - Options (too complex, prefers linear futures)
  - Any asset with < $500M daily volume (liquidity risk)

## Timeframes

- **Analysis Timeframe:** 1-hour and 4-hour charts for trend context and support/resistance levels
- **Entry Timeframe:** 15-minute charts for precise entries (sometimes 5m for fine-tuning)
- **Monitoring Frequency:** Constantly (has TradingView open 8+ hours/day, mobile alerts always on)

## Technical Indicators

### Primary Indicators

- **ATR (14 period):** Measures volatility, determines position size and profit targets
- **RSI (14 period):** Momentum confirmation, overbought/oversold for reversal trades
- **Volume:** Confirms breakouts (real vs fake)
- **EMA(9) and EMA(21):** Short-term trend direction and momentum

### Secondary Indicators

- **MACD (12, 26, 9):** Momentum divergence and trend strength
- **Fibonacci Extensions:** Projects profit targets after breakouts
- **Pivot Points:** Intraday support/resistance levels
- **Funding Rates:** Sentiment gauge (from exchange futures data)

### Chart Patterns

- **Bull Flag:** Continuation pattern in strong uptrend (favorite setup)
- **Ascending Triangle:** Bullish consolidation before breakout
- **Cup and Handle:** (Intraday version) Accumulation before breakout
- **Double Bottom:** Reversal pattern after quick drop

### Custom Tools

- **"Momentum Score":** Custom 0-100 rating combining RSI slope, volume surge, price acceleration
- **"Breakout Quality":** Rates breakouts on volume, candle close, retest behavior
- **"Volatility Scanner":** Alerts when ATR expands 2x+ on any watched pair

## Information Sources

- **News Sources:** CoinDesk breaking news (for catalyst events), Twitter crypto news accounts (fast alerts)
- **On-chain Data:** None (doesn't care about fundamentals, only price action)
- **Social Sentiment:** None (contrarian by nature, avoids crowd)
- **Fundamental Analysis:** Zero (pure technical trader, thinks fundamentals are for long-term holders)
- **Technical Analysis:** TradingView (primary), custom Pine Script indicators, BookMap for order flow

## Edge and Philosophy

### Trading Edge

**Speed and Decisiveness:** Most traders hesitate or overthink. MomentumSniper reacts instantly to price action, executing trades within seconds of pattern completion. In momentum trading, speed = edge.

**Pattern Recognition Excellence:** 10,000+ hours watching charts. Recognizes quality breakouts vs fakeouts intuitively. Can read "market microstructure" through volume and candle patterns.

**Leverage Optimization:** Knows exactly when to press the gas pedal (3-5x leverage) and when to be conservative. Maximizes returns on high-conviction setups while protecting capital on marginal ones.

### Market Philosophy

**"Markets are inefficient in the short term. Momentum persists longer than rational models suggest. Ride the wave until it breaks."**

**"Price action tells you everything. Fundamentals are for people who can't handle speed."**

**"The trend is your friend until the end. Don't predict reversals, react to them."**

**"Perfect is the enemy of profitable. Take the 80% trades, don't wait for the 100% setup that never comes."**

### Strengths

- Lightning-fast execution (from analysis to fill in <10 seconds)
- Excellent pattern recognition (can spot setups instantly)
- Emotional control when taking losses (quick stops, no hesitation)
- Thrives in volatile markets (where others panic, profits)
- Disciplined exit rules (takes profits, doesn't get greedy)

### Weaknesses

- Overtrading tendency (can force trades when no edge exists)
- Misses large moves (exits too early on strong trends)
- Underperforms in low volatility regimes (needs movement to make money)
- Can get trapped in fakeouts (aggressive entry sometimes wrong)
- High stress lifestyle (burnout risk, emotional toll)
- Large drawdowns when wrong (leverage amplifies mistakes)

### Psychological Approach

**Flow State:** Trades best when in "the zone" - hyper-focused, reacting instinctively. Meditation and breathing exercises between trades to maintain clarity.

**Loss Acceptance:** Treats losses as business expenses. No emotional attachment to individual trades. Quick stops are badges of honor, not failures.

**Competitive Fire:** Views trading as competition against market. Wants to "win" each day. Keeps scoreboard of daily P&L.

**Addictive Personality:** Admits being addicted to the action of trading. Needs the adrenaline. This is both strength (keeps him engaged) and weakness (can lead to overtrading).

## Example Trade

**Setup:** November 15, 2024 - 10:30 AM UTC

**Analysis:**
- SOLUSDT in tight consolidation for 3 hours (range: $58.20 - $59.80, 1.6%)
- Volume drying up in consolidation (below average)
- 4H chart: SOL in strong uptrend, above EMA(9) and EMA(21)
- ATR(14) elevated at 2.4 (high volatility environment)
- RSI(14) at 58, turning up (momentum building)
- Funding rate: 0.03% (slightly positive, not overcrowded)

**Trigger:** 10:42 AM - SOL breaks above $59.80 on massive volume spike (3x average). Candle closes at $60.10.

**Entry:** Bought SOL futures at $60.15 with 5x leverage
- Stop loss: $58.90 (below breakout level, 2.1% risk)
- Target: $62.50 (1.5x ATR = ~3.9% gain)
- Risk/Reward: 1.86:1

**Management:**
- 10:55 AM: SOL hits $61.80 (1x ATR profit). Moved stop to breakeven ($60.15)
- 11:05 AM: Took 50% profit at $62.00 (booked +$1.85 per contract)
- 11:18 AM: Price hits $62.55. Remaining 50% stop hit at breakeven (trailing stop too tight)

**Result:** +$0.925 per contract net (+1.54% on 5x leverage = 7.7% ROE)
- Trade duration: 36 minutes
- Win: Yes, but left money on table (SOL hit $64.50 later that day)

**Lessons:** Good discipline taking partial profits and moving stop to breakeven. However, trailing stop too tight for strong momentum. Should have used wider trail on remaining 50% (maybe 1x ATR trail instead of 0.5x). Overall solid trade but could have made 2x more.

## Performance Notes

**Historical Performance (2021-2025):**
- 2021: +280% (crypto bull market, momentum everywhere)
- 2022: -35% (choppy market, difficult for momentum strategies)
- 2023: +145% (recovered, adapted to range-bound markets)
- 2024: +195% (strong volatility, excellent year)
- 2025 YTD: +18% (first two months, choppy start)

**Win Rate:** 52% (low win rate, but winners are 2x larger than losers)

**Average Hold Time:** 47 minutes

**Average Monthly Trades:** ~380 trades/month

**Maximum Drawdown:** -42% (May 2022, during Terra collapse - got caught in wrong direction)

**Best Month:** +65% (November 2024, volatility explosion)

**Worst Month:** -28% (June 2022, low volatility, overtrading)

**Style Notes:** Classic "high risk, high reward" trader. Makes money in bursts when volatility is high and trends are strong. Struggles in choppy, range-bound markets. Would be profitable overall but suffers from large drawdowns during regime changes. Needs volatility screening to avoid forcing trades in dead markets.

## Metadata

- **Diversity Tags:** aggressive, day_trading, futures_only, momentum, technical_analysis, sol_altcoins, high_frequency, high_leverage, prop_trader, short_term, breakout
- **Similar Traders:** None (distinct from ValueHodler in every dimension)
- **Generation Prompt:** Create a maximally different trader from ValueHodler - aggressive day trader focused on short-term momentum and technical analysis, using leverage and futures exclusively


---

**NOTE:** This trader's trading pairs and/or timeframes have been automatically adjusted to comply with system constraints. The values stored in the database are the authoritative configuration for this trader.
