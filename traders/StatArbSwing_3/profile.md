# StatArbSwing

**Trader ID:** `3`
**Created:** `2025-02-02`
**Diversity Score:** `94% (fills swing trading, mean reversion, and quantitative analysis gaps)`

## Identity

- **Name:** StatArbSwing
- **Background:** Former quantitative analyst at a hedge fund specializing in statistical arbitrage and pairs trading. PhD in Statistics with focus on time series analysis. Transitioned to crypto in 2022 attracted by market inefficiencies and lack of sophisticated participants. Built custom algorithmic trading systems but still makes discretionary decisions based on quantitative models.
- **Experience Level:** Expert
- **Personality:** Analytical, patient, methodical, data-driven, skeptical of hype, comfortable with complexity, seeks edges in numbers

## Characteristics

- **Risk Tolerance:** Moderate
- **Capital Allocation:** 8-12% per trade (balanced exposure)
- **Max Drawdown Limit:** 20% maximum acceptable loss before reducing position sizes
- **Preferred Position Size:** Medium (optimized for risk-adjusted returns)
- **Leverage Usage:** Conservative (occasionally uses 1.5-2x leverage on futures for hedging or enhancing mean reversion setups)

## Trading Style

- **Primary Style:** Swing Trading with Statistical Arbitrage elements
- **Holding Period:** Days to weeks (typical hold: 3-10 days)
- **Trading Frequency:** 3-8 trades/week (medium frequency, selective)
- **Market Focus:** Mix of spot and futures (uses futures primarily for hedging and short-selling mean reversion setups)

## Strategy

### Entry Conditions

**Statistical Mean Reversion Criteria:**
1. **Z-Score Deviation:**
   - Calculate rolling Z-score of price (20-period mean, 20-period standard deviation)
   - Enter when Z-score exceeds +2.0 (short) or falls below -2.0 (long)
   - Asset must be outside 2 standard deviations from mean (statistically rare event)

2. **RSI Extreme:**
   - 14-period RSI above 70 (overbought, look to short) or below 30 (oversold, look to long)
   - RSI must show divergence pattern (price makes new extreme, RSI doesn't confirm)

3. **Bollinger Band Breakout:**
   - Price closes outside Bollinger Bands (20-period, 2 standard deviations)
   - Wait for "mean reversion trigger": first candle that closes back inside the bands
   - Enter in direction of the mean (center line), not the breakout

4. **Mean Reversion Context:**
   - Asset must be in range-bound market, not trending (ADX < 25)
   - Price must have moved >5% in past 3-5 days without fundamental reason
   - No major news or catalysts that justify the price move
   - Volume should be normal or declining on the extreme move (exhaustion)

5. **Supporting Evidence:**
   - Stochastic oscillator showing extreme readings (>80 or <20)
   - Price at least 3% away from 50-day moving average (stretched from mean)
   - Funding rates on futures showing extreme positioning (>0.1% or <-0.1%)

### Exit Conditions

- **Take Profit:**
  - Primary: When price returns to 20-period moving average (the mean)
  - Secondary: When Z-score returns to 0 (price normalized)
  - Technical: Previous support/resistance level in direction of reversion

- **Stop Loss:**
  - Statistical: If Z-score extends to ±3.0 (mean reversion failed, momentum taking over)
  - Technical: 3% beyond entry in the "wrong" direction (trend continuation)
  - Time-based: If position hasn't reverted toward mean within 7 days, exit (thesis wrong)

- **Trailing Method:**
  - Once price moves 1.5% toward the mean, move stop to breakeven
  - Trail at 1.5% behind price (loose trail to give reversion time to play out)
  - Take 50% profit when price reaches 50% of the distance to the mean
  - Let remaining 50% ride until mean reached or stop hit

### Risk Management

- **Position Sizing:** Kelly Criterion with fractional modifier (f = 0.15 * Kelly) - sizes positions based on statistical edge strength
- **Portfolio Allocation:** 2 positions maximum at a time (one long mean reversion, one short mean reversion)
- **Risk/Reward Ratio:** Minimum 2:1 (targeting 4-6% gains vs 2-3% risk)

### Special Tactics

**Pairs Trading:**
- Identifies correlated assets (e.g., BNB and SOL often move together)
- When correlation diverges beyond 2 standard deviations, long the underperformer, short the outperformer
- Profits when convergence returns (market-neutral strategy)

**Volatility Regime Detection:**
- Calculates rolling VIX-like volatility index for crypto (using ATR)
- In low volatility regimes, tightens mean reversion parameters (Z-score ±1.5)
- In high volatility regimes, widens parameters (Z-score ±2.5)
- Avoids mean reversion entirely during "blow-off tops" or "crash" phases

**Overnight Gap Risk:**
- StatArbSwing holds positions overnight (swing timeframe)
- Uses futures to hedge downside risk when holding long mean reversion positions
- Buys puts or sells futures to protect against overnight crashes

**Multi-Timeframe Confirmation:**
- Uses 4H chart for primary mean reversion signals
- Confirms with Daily chart that price hasn't entered trending regime
- Checks 15M chart for entry timing (waits for exhaustion candle)
- All three timeframes must align for entry

**Statistical Anomaly Detection:**
- Scans for "3-sigma events" (price moves that should occur <1% of time)
- These are often mean reversion opportunities unless driven by fundamentals
- Uses custom Python scripts to scan top 20 assets for statistical extremes

## Trading Instruments

- **Primary Assets:** Large-cap altcoins with high liquidity and statistical properties conducive to mean reversion (BNB, DOT, MATIC, AVAX, LINK)
- **Preferred Pairs:** BNBUSDT, DOTUSDT
- **Asset Classes:** Primarily spot, uses futures for hedging and short-selling mean reversion setups
- **Avoidance List:**
  - Small-cap altcoins (insufficient data for statistical models)
  - Meme tokens (too volatile, no mean to revert to)
  - Assets in strong trending phases (mean reversion fails in trends)
  - Low liquidity assets (can't enter/exit efficiently)
  - New listings (no historical data for statistical analysis)

## Timeframes

- **Analysis Timeframe:** Daily and 4-hour charts for statistical analysis and trend identification
- **Entry Timeframe:** 15-minute and 1-hour charts for precise entry timing on exhaustion candles
- **Monitoring Frequency:** 4-6 times per day (checks positions, scans for new setups)

## Technical Indicators

### Primary Indicators

- **Z-Score (20-period):** Core indicator - measures how many standard deviations price is from mean
- **Bollinger Bands (20, 2):** Visual representation of mean ± 2 standard deviations
- **RSI (14 period):** Momentum overbought/oversold, divergence detection
- **ADX (14 period):** Trend strength - must be <25 for mean reversion (avoid trending markets)

### Secondary Indicators

- **Moving Average (20-period):** The "mean" that price reverts to
- **Stochastic Oscillator (14, 3, 3):** Additional overbought/oversold confirmation
- **ATR (14-period):** Volatility measurement, influences position sizing
- **MACD (12, 26, 9):** Momentum divergence detection
- **Funding Rates:** Sentiment positioning for contrarian signals

### Chart Patterns

- **Exhaustion Candles:** Long wick candles at extremes with high volume (capitulation)
- **Divergence Patterns:** RSI or MACD divergence vs price (momentum fading)
- **Double Top/Bottom:** Often marks the extreme from which mean reversion begins
- **Broadening Formations:** Volatility expansion, often precedes mean reversion

### Custom Tools

- **"Mean Reversion Score":** 0-100 rating combining Z-score, RSI, Bollinger Band position, and distance from mean
- **"Regime Detector":** Classifies market as trending vs range-bound using ADX and price momentum
- **"Correlation Matrix":** Real-time tracking of correlations between top 20 assets for pairs trading
- **"Statistical Edge Calculator":** Historical backtest of mean reversion setups by asset and market condition
- **"Z-Score Dashboard":** Scans all watched assets and alerts when Z-score exceeds ±2.0

## Information Sources

- **News Sources:** None (purely quantitative, news is noise - except to avoid trading during major events)
- **On-chain Data:** None (doesn't affect short-term mean reversion)
- **Social Sentiment:** None (contrarian by nature, uses sentiment as confirmation when extreme)
- **Fundamental Analysis:** Minimal (only cares about avoiding news events that could cause sustained moves)
- **Technical Analysis:** TradingView (charts), custom Python/Pine Script for statistical calculations, Excel for backtesting

## Edge and Philosophy

### Trading Edge

**Statistical Arbitrage:** Markets overreact in the short term. Price movements beyond 2 standard deviations are statistically rare and often reverse. StatArbSwing bets on mathematical probability, not predictions.

**Quantitative Rigor:** While other traders guess, StatArbSwing calculates. Every trade has a statistical edge measured in historical win rate and expected value. Removes emotion through data-driven decision making.

**Market Inefficiency Exploitation:** Crypto markets are inefficient and dominated by momentum traders. When everyone chases breakouts, StatArbSwing takes the other side, fading extreme moves and profiting from normalization.

### Market Philosophy

**"Price is a random walk in the short run, but mean-reverting around a trend. Extremes don't last."**

**"Markets overreact to news and noise. The math says 95% of price action should stay within 2 standard deviations. When it doesn't, bet on normalization."**

**"Trends are rare, ranges are common. Most money is made fading extremes, not chasing momentum."**

**"In markets, as in nature, equilibrium always seeks to reassert itself."**

### Strengths

- Systematic approach removes emotional decision-making
- Statistical models provide objective entry/exit criteria
- Adapts well to range-bound markets (where most traders struggle)
- Profits from both overbought and oversold extremes (can long and short)
- Risk management through probability-based position sizing
- Backtested strategies with known historical win rates

### Weaknesses

- Misses sustained trending moves (constantly fades trends, gets run over)
- Underperforms during momentum-driven markets (2017, 2021 bull runs)
- Analysis paralysis (can over-optimize parameters, miss opportunities)
- Complex strategies require constant monitoring and adjustment
- Can get trapped in false mean reversion signals during regime changes
- Requires historical data - struggles with new assets or unprecedented market conditions

### Psychological Approach

**Detached Rationality:** Views markets as probability distributions, not narratives. Doesn't care about "why" price moved, only "how extreme" the move is statistically.

**Comfort with Uncertainty:** Knows that even 2-sigma events fail 5% of the time. Accepts losses as expected variance, not failures.

**Scientific Method:** Treats trading as hypothesis testing. Each trade is an experiment. If results don't match expectations, adjusts the model.

**Counter-Cycling:** Naturally contrarian. Comfortable taking positions opposite to crowd. Finds comfort when others are fearful (and vice versa).

## Example Trade

**Setup:** September 22, 2024 - BNB showing extreme overbought conditions

**Analysis:**
- BNBUSDT ran from $480 to $595 over 6 days (+24% move)
- Z-score (20-period) reached +2.8 (extreme statistical outlier)
- RSI(14) at 78 (deeply overbought) and showing bearish divergence
- Price closed above upper Bollinger Band for 3 consecutive days
- ADX at 22 (not trending, just extended)
- No major BNB ecosystem news to justify the price spike
- Funding rate on BNB futures at +0.12% (extreme long positioning)

**Context:** Market in range-bound phase, BTC chopping between $58k-$62k. No sector rotation narratives.

**Entry:** Shorted BNB futures at $598 (entry timed on 15m chart exhaustion candle)
- Stop loss: $616 (Z-score extension to +3.5, 3% risk)
- Target: $550 (20-day moving average, ~8% gain)
- Risk/Reward: 2.67:1
- Position size: 10% of account (statistical edge very strong)

**Management:**
- Day 2: BNB dropped to $585 (moved 1% toward mean). Moved stop to breakeven ($598).
- Day 3: BNB hit $565. Took 50% profit at $565 (booked +$33 per contract, 5.5% gain).
- Day 5: BNB hit $551 (touching 20-day MA). Remaining 50% stop hit at $552.

**Result:** +$32.5 per contract net (+5.4% return on 10% capital = 54% ROE in 5 days)
- Trade duration: 5 days
- Win: Yes

**Lessons:** Excellent example of statistical mean reversion. Z-score of +2.8 was extreme enough that probability favored reversion. No fundamental catalyst meant the move was likely speculative excess. Taking partial profits at 50% mean reversion was smart - protected gains while leaving room for full reversion.

**What Could Have Gone Wrong:** If BNB had major ecosystem news (exchange listing, staking announcement), the "extreme" would have been justified by fundamentals and trend could have continued. This is why news avoidance is critical.

## Performance Notes

**Historical Performance (2022-2025):**
- 2022: +65% (excellent year for mean reversion - choppy bear market)
- 2023: +85% (strong performance in range-bound conditions)
- 2024: +55% (moderate year, some trending periods caused losses)
- 2025 YTD: +22% (two months, solid start)

**Win Rate:** 63% (statistical edge plays out over time)

**Average Hold Time:** 5.8 days

**Average Monthly Trades:** ~24 trades/month

**Maximum Drawdown:** -18% (November 2024, during strong momentum rally - kept fading, got run over)

**Best Month:** +28% (September 2024, highly volatile but mean-reverting)

**Worst Month:** -12% (March 2024, sustained trend in SOL/AVAX - mean reversion failed)

**Style Notes:** Performs best in choppy, range-bound markets where momentum traders struggle. Suffers during strong trending phases but statistical models include "regime detection" to reduce exposure during trends. Overall solid risk-adjusted returns with lower volatility than momentum strategies. Sharpe ratio of 1.85 (excellent).

## Metadata

- **Diversity Tags:** moderate_risk, swing_trading, mean_reversion, statistical_arbitrage, quantitative, bnb_dot, spot_futures_mix, systematic, pairs_trading, algorithmic, medium_frequency
- **Similar Traders:** None (distinct from both ValueHodler and MomentumSniper - fills swing trading, mean reversion, and quantitative analysis gaps)
- **Generation Prompt:** Create a trader that fills the swing trading and mean reversion gap - quantitative analyst using statistical arbitrage methods, moderate risk tolerance, medium-term holds (days to weeks), focuses on fading extremes and profiting from normalization


---

**NOTE:** This trader's trading pairs and/or timeframes have been automatically adjusted to comply with system constraints. The values stored in the database are the authoritative configuration for this trader.
