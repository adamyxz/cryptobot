# Trader Generation Guide for Claude Code

## CRITICAL SYSTEM REQUIREMENT: PERPETUAL FUTURES ONLY

⚠️ **This system is exclusively for perpetual futures trading.** All generated traders MUST be designed for perpetual futures markets with the following mandatory capabilities:

1. **Long AND Short Trading**: Every trader must be willing and able to take both long and short positions
2. **Leverage Usage**: Leverage is a core feature (minimum 1x, typical 2-10x depending on strategy)
3. **Contract-Specific Understanding**: Traders must understand and utilize:
   - Funding rates (as either cost or opportunity)
   - Liquidation prices and risk management
   - Perpetual futures mechanics (mark price, index price, etc.)
4. **No Spot-Only Traders**: Traders who "only go long" or "avoid leverage/futures" are INVALID for this system

**This is a hard requirement.** Any trader profile that doesn't support both long and short trading in perpetual futures will be rejected.

## Objective

Generate unique, diverse cryptocurrency trading strategy profiles as markdown files. Each trader must be **distinctly different** from existing traders to ensure a rich variety of trading approaches.

## Critical Requirement: DIVERSITY

**The existing traders summary is provided in the instructions - use it to ensure diversity!**

1. Review the existing traders summary provided in the instructions
2. Analyze their characteristics, trading styles, strategies, and approaches
3. Ensure your new trader is **significantly different** from all existing traders

**Diversity Dimensions (within perpetual futures):**
- Risk tolerance (conservative vs aggressive)
- Trading style (day trading, swing trading, position trading, scalping, HFT, market making, arbitrage)
- Directional bias (trend-following, mean-reversion, neutral, opportunistic)
- Timeframe preference (1m scalping vs weekly position trading)
- Technical approach (price action, indicators, statistical arbitrage, ML-based)
- Asset classes (BTC-only, altcoins, DeFi tokens, stablecoins for hedging)
- Leverage philosophy (conservative 1-2x vs moderate 3-5x vs aggressive 10x+)
- Experience level (novice retail, institutional, algorithmic)

## Trader Profile Template

Each trader file MUST follow this structure:

```markdown
# <Trader Name>

**Trader ID:** `<numeric_id>` (format: auto-increment number provided in instructions)
**Created:** `<date>`
**Diversity Score:** `<estimated_similarity_vs_existing>`

## Identity

- **Name:** `<descriptive name>`
- **Background:** `<brief background - retail, institutional, ex-engineer, etc.>`
- **Experience Level:** `<beginner/intermediate/advanced/expert>`
- **Personality:** `<personality traits affecting trading - patient, impulsive, analytical, intuitive, etc.>`

## Characteristics

- **Risk Tolerance:** `<conservative/moderate/aggressive/very_aggressive>`
- **Capital Allocation:** `<percentage per trade>`
- **Max Drawdown Limit:** `<maximum acceptable loss>`
- **Preferred Position Size:** `<small/medium/large>`
- **Leverage Usage:** `<conservative (1-2x) / moderate (2-5x) / aggressive (5-10x) / very_aggressive (10x+)>` (MUST use leverage - no "none" option)
- **Short Selling Willingness:** `<always / when_signals_align / rarely / only_for_hedging>` (MUST be willing to short)
- **Directional Bias:** `<long_biased / short_biased / direction_neutral / opportunistic_both>`

## Trading Style

- **Primary Style:** `<day_trading/swing_trading/position_trading/scalping/HFT/market_making/arbitrage>`
- **Holding Period:** `<minutes/hours/days/weeks/months>`
- **Trading Frequency:** `<1-5 trades/day / 5-20 trades/day / 20+ trades/day>`
- **Market Focus:** `<perpetual_futures> (MANDATORY - all traders must use perpetual futures, no exceptions)`

## Strategy

### Entry Conditions

`<Detailed description of when to enter a trade>`

### Exit Conditions

- **Take Profit:** `<TP strategy>`
- **Stop Loss:** `<SL strategy>`
- **Trailing Method:** `<if applicable>`

### Risk Management

- **Position Sizing:** `<formula or approach>`
- **Portfolio Allocation:** `<how capital is distributed>`
- **Risk/Reward Ratio:** `<minimum acceptable R:R>`

### Special Tactics

`<Any unique strategies, patterns, or edge cases>`

## Trading Instruments

- **Primary Assets:** `<BTC/ETH/altcoins/stablecoins/etc.>`
- **Preferred Pairs:** `<specific trading pairs>`
- **Asset Classes:** `<list preferred asset types>`
- **Avoidance List:** `<assets or conditions this trader won't touch>`

## Timeframes

- **Analysis Timeframe:** `<higher timeframe for context>`
- **Entry Timeframe:** `<lower timeframe for precision>`
- **Monitoring Frequency:** `<how often they check charts>`

## Technical Indicators

### Primary Indicators

`<List most important indicators with usage>`

### Secondary Indicators

`<Supporting indicators>`

### Chart Patterns

`<Patterns they look for (flags, wedges, H&S, etc.)>`

### Custom Tools

`<Any proprietary or unique analysis methods>`

## Information Sources

- **News Sources:** `<Bloomberg, CoinDesk, Twitter, etc.>`
- **On-chain Data:** `<Glassnode, Nansen, etc.>`
- **Social Sentiment:** `<sources for sentiment analysis>`
- **Fundamental Analysis:** `<how they evaluate fundamentals>`
- **Technical Analysis:** `<primary tools and methods>`

## Required Data Sources

**CRITICAL:** This section defines what market data the trader requires for decision-making. The system will automatically fetch these indicators before each decision.

**Strategy Keywords:** `<comma-separated keywords that map to required indicators>`

Available keyword mappings:
- `price_action`, `ohlcv`, `trend`, `momentum` → market_data (OHLCV data)
- `funding_rate`, `funding`, `futures` → fundingratehistory
- `orderbook`, `order_flow`, `liquidity`, `depth` → fetch_orderbook
- `open_interest`, `oi`, `leverage` → fetch_open_interest
- `long_short_ratio`, `lsr`, `sentiment`, `positioning` → longshortratio
- `liquidation`, `squeeze` → fetch_orderbook + longshortratio
- `arbitrage`, `basis` → fetch_orderbook + fundingratehistory

**Example:**
```yaml
Strategy Keywords: price_action, funding_rate, liquidation, sentiment

This will automatically fetch:
- market_data.py (for price_action)
- fundingratehistory.py (for funding_rate)
- fetch_orderbook.py (for liquidation)
- longshortratio.py (for sentiment)
```

**Custom Indicators:** `<list any additional scripts from indicators/ directory needed>`

## Edge and Philosophy

### Trading Edge

`<What gives this trader an advantage over the market>`

### Market Philosophy

`<Beliefs about how markets work>`

### Strengths

`<What this trader does well>`

### Weaknesses

`<Areas of vulnerability or known issues>`

### Psychological Approach

`<How they handle emotions, discipline, mindset>`

## Example Trade

**Setup:** `<market conditions leading to trade>`

**Analysis:** `<reasoning behind the trade>`

**Entry:** `<entry price and timing>`

**Exit:** `<exit price and timing>`

**Result:** `<outcome and lessons learned>`

## Performance Notes

`<Any historical performance data or expectations>`

## Metadata

- **Diversity Tags:** `<keywords for categorization>`
- **Similar Traders:** `<none if unique, or list similar existing traders>`
- **Generation Prompt:** `<original user prompt, if any>`
```

## Generation Process

### Step 1: Review Provided Trader Summary

The existing traders summary is already provided in your instructions, showing:
   - Trader IDs
   - Trading styles
   - Risk tolerance
   - Trading pairs
   - Timeframes

Use this summary to understand what already exists.

### Step 2: Identify Gaps

Determine what combinations are **missing** or **underrepresented**:

- Are all traders aggressive? Create a conservative one.
- All focused on BTC? Create an altcoin specialist.
- All using technical analysis? Create a fundamental analyst.
- All short-term? Create a long-term position trader.
- All discretionary? Create a systematic algorithmic trader.
- All trend-following? Create a mean-reversion or market-neutral trader.
- All willing to short aggressively? Create a more conservative short-only-hedging trader.

### Step 3: Design Unique Trader

Choose characteristics that **maximize diversity**:

- **If user provided a prompt:** Incorporate their requirements but still ensure diversity
- **If no prompt:** Randomly select from underrepresented combinations
- **Target:** Create someone who would trade **differently** from 80%+ of existing traders

### Step 4: Generate Trader File

1. **IMPORTANT:** Use the NUMERIC ID provided in the instructions (e.g., 1, 2, 3, etc.)
2. Create a FOLDER named `<TraderName>_<numeric_id>/`
3. Inside that folder, create a file named `profile.md`
   - Example: `BitcoinMaximalist_1/profile.md`
   - Example: `QuantumTrader_2/profile.md`
   - Example: `CryptoWhisperer_3/profile.md`
4. Fill in ALL sections of the template
5. Ensure internal consistency (e.g., conservative risk tolerance matches position sizing)
6. Make the trader feel **real** and **nuanced** - not a caricature
7. **CRITICAL:** Only select trading pairs from the provided list (mainstream, high-volume pairs)

### Step 5: Validate Diversity

Before finalizing, ask yourself:
- Would this trader make similar decisions to existing traders?
- If they were in a room with all other traders, would they stand out?
- Do they bring a genuinely different perspective?

**If yes to diversity:** Create the file
**If no:** Modify characteristics to increase differentiation

## Quality Guidelines

### Do's ✅

- Create traders with realistic strengths AND weaknesses
- Include specific, actionable strategies (not vague platitudes)
- Add personality and background that informs trading decisions
- Describe clear entry/exit rules
- Explain the reasoning behind each approach
- Make traders internally consistent

### Don'ts ❌

- Don't create perfect traders (they don't exist)
- Don't use generic advice ("buy low, sell high")
- Don't copy existing traders with minor changes
- Don't ignore risk management
- Don't make unrealistic claims
- Don't leave template placeholders unfilled
- **NEVER create spot-only traders** (violates system purpose)
- **NEVER create traders who refuse to short** (perpetual futures require双向交易能力)
- **NEVER set Leverage Usage to "none"** (perpetual futures always use leverage, minimum 1x)

## Example Diversity Matrix

When designing traders, vary across these axes (ALL within perpetual futures):

| Axis | Options |
|------|---------|
| **Risk** | Conservative, Moderate, Aggressive, Very Aggressive |
| **Style** | Day Trading, Swing Trading, Position Trading, Scalping, HFT, Market Making, Arbitrage |
| **Directional Bias** | Long-Biased, Short-Biased, Direction-Neutral, Opportunistic (Both) |
| **Leverage** | Conservative (1-2x), Moderate (2-5x), Aggressive (5-10x), Very Aggressive (10x+) |
| **Asset** | BTC-only, ETH-centric, Altcoins, DeFi, Diversified |
| **Analysis** | Pure Technical, Fundamental, Sentiment, On-chain, Hybrid, Quant |
| **Timeframe** | Sub-minute, 1m-15m, 1h-4h, Daily, Weekly |
| **Decision** | Discretionary, Systematic, Algorithmic |
| **Experience** | Retail Beginner, Retail Experienced, Prop Trader, Institutional, Quant |

**⚠️ CRITICAL: The "Focus" axis is FIXED as Perpetual Futures for ALL traders.**

## Final Instructions

When the user invokes `/newtrader`:

1. **ALWAYS** review the existing traders summary provided in the instructions
2. **ALWAYS** analyze what's missing or underrepresented
3. **ALWAYS** create someone distinctly different
4. **NEVER** skip the diversity check
5. **Create exactly ONE trader** unless explicitly told to create more
6. **Use the NUMERIC ID** provided in the instructions (e.g., 1, 2, 3, etc.)
7. **Create a folder** `<TraderName>_<numeric_id>/` with `profile.md` inside
   - Example: `BitcoinMaximalist_1/profile.md`, `QuantumTrader_2/profile.md`, etc.
8. **ONLY select trading pairs from the provided list** (mainstream, high-volume pairs like BTCUSDT, ETHUSDT, etc.)
9. **MANDATORY: Every trader MUST support both LONG and SHORT trading** - this is a perpetual futures system
10. **MANDATORY: Every trader MUST use leverage** (minimum 1x, should be specified in profile)
11. **Market Focus is ALWAYS "Perpetual Futures"** - never deviate from this

Your goal is to build a diverse community of traders, each with their own unique approach to **perpetual futures trading** in the cryptocurrency markets.
