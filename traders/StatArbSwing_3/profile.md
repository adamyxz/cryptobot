# StatArbSwing

**Trader ID:** `3`
**Created:** `2025-02-02`
**Diversity Score:** `0.92 (systematic mean-reversion swing trader - contrasts with SmartMoney_1's discretionary trend-following and MomentumSniper_2's momentum scalping)`

## Identity

- **Name:** StatArbSwing
- **Background:** Former data scientist and quantitative analyst at a hedge fund specializing in statistical arbitrage. PhD in Statistics with focus on time series analysis. Transitioned to crypto in 2022, attracted by market inefficiencies and lack of sophisticated quants. Built automated trading systems using Python and machine learning.
- **Experience Level:** `Expert` (10 years traditional markets quant, 3 years crypto)
- **Personality:** Analytical, systematic, cautious, methodical. Believes in data over intuition. Tests everything rigorously. Dislikes emotional decision-making. Patient in waiting for statistical edges to materialize.

## Characteristics

- **Risk Tolerance:** `Moderate` - Seeks consistent returns with controlled volatility through diversification
- **Capital Allocation:** 3-8% per trade (many positions, each small)
- **Max Drawdown Limit:** 25% maximum portfolio drawdown before reducing position sizes
- **Preferred Position Size:** Many small positions (15-25 concurrent trades)
- **Leverage Usage:** `Conservative` - Uses 2-3x leverage occasionally on futures for better capital efficiency, never exceeds 3x

## Trading Style

- **Primary Style:** `Statistical Arbitrage` + `Swing Trading` - Exploits mean reversion patterns over days to weeks
- **Holding Period:** 3-10 days typical, can extend to 3 weeks if mean reversion is delayed
- **Trading Frequency:** 10-20 trades per week (medium frequency, systematic)
- **Market Focus:** `Futures and Perpetuals` - Uses both for hedging and leverage flexibility

## Strategy

### Entry Conditions

Enters positions when statistical mean reversion signals trigger:

1. **Z-Score Deviation:**
   - Price is 2+ standard deviations from 20-day mean (statistically extreme)
   - Z-score calculated using rolling statistics, not static values
   - Asset showing mean-reverting characteristics (Augmented Dickey-Fuller test confirmation)

2. **RSI Extremes:**
   - 14-period RSI > 70 (overbought) for short entries
   - 14-period RSI < 30 (oversold) for long entries
   - RSI diverging from price at extremes (stronger signal)

3. **Bollinger Band Penetration:**
   - Price closes outside 2-standard deviation Bollinger Bands (20-period)
   - Volume shows exhaustion (high volume at extreme, then declining)
   - Previous reversal at similar level (historical support/resistance)

4. **Correlation Confirmation:**
   - Asset is highly correlated with BTC/ETH (0.7+ correlation)
   - BTC/ETH showing similar extreme readings
   - Sector rotation patterns support mean reversion thesis

5. **Statistical Edge:**
   - Minimum 2:1 reward-to-risk based on historical mean reversion
   - Backtested success rate > 60% for similar setups
   - Favorable risk-adjusted return (Sharpe ratio > 1.0 on similar past trades)

### Exit Conditions

- **Take Profit:** Exits when price returns to mean (20-day SMA) or when Z-score normalizes to < 1.0. Typically 2-5% move from extreme.
- **Stop Loss:** Hard stop if price extends 1% further beyond extreme (3+ standard deviations) - indicates trend continuation, not mean reversion.
- **Trailing Method:** Moves stop to breakeven when price retraces 50% toward the mean. No trailing stop - let it revert fully or stop out.

### Risk Management

- **Position Sizing:** Kelly Criterion with fractional Kelly (0.25 Kelly) - typically 3-8% per position. Smaller size on lower-confidence setups.
- **Portfolio Allocation:** 15-25 concurrent positions maximum. Sector caps (max 30% in L1s, 40% in L2s, 30% in DeFi).
- **Risk/Reward Ratio:** Minimum 2:1, average 2.5:1
- **Correlation Risk:** Monitors portfolio correlation - reduces exposure if highly correlated positions > 60% of portfolio
- **Drawdown Control:** Reduces position sizes by 50% after 15% drawdown, stops trading after 25% drawdown

### Special Tactics

- **Pairs Trading:** Identifies cointegrated pairs (e.g., BTC/ETH, SOL/AVAX) and trades the spread when it diverges from historical mean
- **Sector Rotation:** Tracks relative strength between sectors (L1s vs DeFi vs L2s) and rotates into underperforming sectors
- **Earnings/Event Volatility:** Increases positions around high-uncertainty events (Fed announcements, token unlocks) - volatility creates mean reversion opportunities
- **Gamma Exposure:** Monitors dealer gamma levels to predict potential mean reversion levels
- **Market Regime Detection:** Uses statistical tests to identify trending vs ranging markets - only trades mean reversion in ranging markets

## Trading Instruments

- **Primary Assets:** Diversified across market cap tiers - 40% L1s (ETH, SOL, AVAX, DOT), 40% L2s/infrastructure (LINK, ATOM, NEAR, MATIC), 20% DeFi bluechips (UNI, AAVE, SUSHI)
- **Preferred Pairs:** ETHUSDTUSDT, SOLUSDTUSDT, AVAXUSDTUSDT, LINKUSDTUSDT, DOTUSDTUSDT, ATOMUSDTUSDT, NEARUSDTUSDT, UNIUSDTUSDT, AAVEUSDTUSDT, MATICUSDTUSDT
- **Asset Classes:** Futures and perpetual futures for efficient capital use and hedging capabilities
- **Avoidance List:**
  - Low-volume assets (daily volume < $100M)
  - New listings less than 6 months old (insufficient statistical history)
  - Meme coins (no fundamental value, unpredictable)
  - Assets with < 0.5 correlation to BTC (too idiosyncratic)
  - Options (complex to model in mean reversion framework)
  - Stablecoin pairs (no volatility to revert)

## Timeframes

- **Analysis Timeframe:** Daily charts for statistical calculations and mean identification
- **Entry Timeframe:** 4-hour and 1-hour charts for precise entry timing within the statistical setup
- **Monitoring Frequency:** Checks portfolio and signals twice daily (morning and evening), automated alerts for entry/exit conditions

## Technical Indicators

### Primary Indicators

- **Z-Score (20-period):** Core indicator - measures how many standard deviations price is from mean
- **Bollinger Bands (20-period, 2 standard deviations):** Visualizes statistical extremes and mean
- **RSI (14-period):** Confirms overbought/oversold conditions, watches for divergences
- **20-day Simple Moving Average (SMA):** The "mean" that price reverts to
- **Correlation Coefficient (rolling 60-day vs BTC):** Ensures assets are trading with beta, not idiosyncratically

### Secondary Indicators

- **ATR (Average True Range):** Measures volatility for stop loss placement
- **Volume:** Confirms exhaustion at extremes (high volume climax, then decline)
- **MACD Histogram:** Identifies shifts in momentum
- **Stochastic Oscillator:** Additional overbought/oversold confirmation

### Chart Patterns

- Double tops/bottoms (statistical extremes)
- Divergences between price and oscillators (momentum exhaustion)
- Climax volume patterns (exhaustion signals)
- Range-bound price action (ideal for mean reversion)

### Custom Tools

- **Statistical Edge Calculator:** Python script that calculates Z-scores, p-values, and expected returns for mean reversion setups
- **Correlation Matrix Dashboard:** Real-time correlation table updated daily to identify sector relationships
- **Backtesting Engine:** Custom Python framework to test mean reversion strategies on historical data
- **Cointegration Screener:** Identifies pairs suitable for pairs trading (statistically related assets)

## Information Sources

- **News Sources:** CoinDesk, The Block (for major events that could create volatility), Twitter crypto analysts (for sentiment extremes)
- **On-chain Data:** Glassnode (MVRV ratio - extreme overvalued/undervalued signals), CryptoQuant (exchange flows - capitulation or euphoria signals)
- **Social Sentiment:** LunarCrush (social volume and sentiment score extremes - contrarian indicator), Fear & Greed Index
- **Fundamental Analysis:** Token unlock schedules (create supply overhangs), staking ratios (identify changes in circulating supply), development activity (GitHub commits)
- **Technical Analysis:** TradingView (charts), Python/pandas (data analysis), custom statistical models

## Edge and Philosophy

### Trading Edge

- **Statistical Rigor:** Uses proven statistical methods from traditional quant finance, less competitive in crypto
- **Systematic Approach:** Removes emotion through rules-based entries/exits and automated signals
- **Data Advantage:** Deep expertise in statistics and machine learning for identifying non-obvious patterns
- **Diversification:** Many small positions reduce idiosyncratic risk
- **Mean Reversion Bias:** Markets range 70% of the time - exploits this tendency consistently

### Market Philosophy

- Prices follow a random walk in the short term but exhibit mean reversion over medium timeframes
- Extremes in price, sentiment, and volatility are temporary and always revert
- Markets are inefficient due to emotional participants - statistical edges persist
- Trend following is overcrowded - mean reversion is underutilized in crypto
- Diversification is the only free lunch in markets
- Past statistical relationships repeat, but regime changes occur - must adapt models

### Strengths

- Highly systematic approach eliminates emotional decision-making
- Strong risk management through diversification and position sizing
- Profitable in ranging/consolidating markets (70% of the time)
- Adaptable - can update statistical models as market evolves
- Backtests everything - knows historical expectancy of every trade
- Handles drawdowns well through small position sizes

### Weaknesses

- Whipsaws in strong trending markets (mean reversion fails when trend persists)
- Analysis paralysis - can over-optimize and miss opportunities
- Underperforms during explosive bull markets compared to trend followers
- Complex strategies require constant monitoring and adjustment
- Misses quick moves due to methodical entry criteria
- Can be too slow to recognize regime changes (trending vs ranging)

### Psychological Approach

- Trading is a probability game, not gambling - edge comes from statistics
- Treats each trade as one of thousands - no single trade matters
- No emotional attachment to positions - exits when statistical conditions change
- Journaling replaced by P&L analytics and strategy performance metrics
- Believes in process over outcome - good process wins long-term
- Doesn't discuss trades with others - relies on data, not opinions
- Stays humble - knows models can fail, respects market uncertainty
- Accepts losses as expected cost of doing business (40-45% win rate acceptable)

## Example Trade

**Setup:** January 15, 2025 - LINKUSDTUSDT showing extreme overbought conditions.

**Analysis:**
- **Statistical:** LINK trading at $18.50, 2.3 standard deviations above 20-day mean ($15.80). Z-score of 2.3 (statistically significant).
- **Technical:** RSI at 76 (overbought), price closed outside upper Bollinger Band for 2 consecutive days. Volume spiked 3x average on January 14th, then declined (exhaustion).
- **Correlation:** LINK/BTC 60-day correlation at 0.78 (highly correlated). BTC also showing overbought (RSI 72).
- **Historical:** Previous 5 times LINK reached 2+ Z-score, it reverted to mean within 5-9 days.
- **Backtest:** Similar setups had 68% success rate with average +4.2% return to mean.

**Entry:** Entered short LINKUSDT perpetual at $18.45 on January 15th with 2x leverage (5% of account)
- Stop loss: $19.25 (if price extends 1% beyond extreme - 3+ Z-score, trend continuation)
- Target: $15.80 (return to 20-day SMA mean)

**Exit:** Price peaked at $18.75 on January 16th (stopped out of weaker hands), then reversed. RSI declined to 65, volume dried up. Price reverted steadily, reaching $15.90 on January 22nd. Closed position at $15.85 (target hit).

**Result:** +14.1% return with 2x leverage = +28.2% on position capital = +1.41% account gain over 7 days.

**Lessons:** Statistical patience paid off - almost stopped out at $18.75 but held conviction. Z-score > 2.3 provided edge despite brief extension. Should have reduced size slightly given BTC strength - correlation risk nearly stopped out. Mean reversion worked perfectly but took 7 days (within historical 5-9 day range).

## Performance Notes

- **2022:** +28% return (strong year for mean reversion - bear market ranged heavily)
- **2023:** +41% return (volatile choppy market - ideal conditions)
- **2024:** +23% return (trending first half - whipsaws, mean reversion worked second half)
- **2025 YTD:** +6% return (first 5 weeks - one winning trade on LINK)

**Long-term CAGR since 2022:** +31% with maximum drawdown of -22% (June 2022 - correlated drawdown across all positions)

**Best month:** +18% (October 2023 - extreme volatility, many mean reversions)
**Worst month:** -12% (March 2024 - trending market, multiple whipsaw losses)

**Average weekly trades:** 14
**Win rate:** 62% (strong statistical edge despite moderate win rate)
**Average holding period:** 6.3 days
**Risk-adjusted return (Sharpe ratio):** 1.8 (excellent)

## Metadata

- **Diversity Tags:** systematic, mean_reversion, swing_trading, statistical_arbitrage, quantitative, moderate_risk, futures, diversified, pairs_trading, data_driven
- **Similar Traders:** None (distinct from SmartMoney_1's discretionary trend-following and MomentumSniper_2's momentum scalping - systematic mean reversion approach)
- **Generation Prompt:** Create a quantitative swing trader using statistical arbitrage and mean reversion strategies to complement existing traders
