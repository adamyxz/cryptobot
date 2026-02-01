# Trader Generation Guide for Claude Code

## Objective

Generate unique, diverse cryptocurrency trading strategy profiles as markdown files. Each trader must be **distinctly different** from existing traders to ensure a rich variety of trading approaches.

## Critical Requirement: DIVERSITY

**Before creating any new trader, you MUST:**

1. Read all existing trader `profile.md` files (located in subdirectories like `TraderName_ID/profile.md`)
2. Analyze their characteristics, trading styles, strategies, and approaches
3. Ensure your new trader is **significantly different** from all existing traders

**Diversity Dimensions:**
- Risk tolerance (conservative vs aggressive)
- Trading style (day trading, swing trading, position trading, scalping, HFT)
- Market focus (spot vs derivatives, futures vs options)
- Timeframe preference (1m scalping vs weekly position trading)
- Technical approach (price action, indicators, statistical arbitrage, ML-based)
- Asset classes (BTC-only, altcoins, DeFi tokens, stablecoins)
- Philosophy (trend following, mean reversion, market making, arbitrage)
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
- **Leverage Usage:** `<none/conservative/moderate/aggressive>`

## Trading Style

- **Primary Style:** `<day_trading/swing_trading/position_trading/scalping/HFT/market_making/arbitrage>`
- **Holding Period:** `<minutes/hours/days/weeks/months>`
- **Trading Frequency:** `<1-5 trades/day / 5-20 trades/day / 20+ trades/day>`
- **Market Focus:** `<spot/futures/options/perpetuals/all>`

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

### Step 1: Survey Existing Traders

1. List all subdirectories containing `profile.md` files
2. Read each `profile.md` file completely
3. Extract key characteristics from each:
   - Trading style
   - Risk tolerance
   - Timeframes
   - Asset preferences
   - Technical approach
   - Philosophy

### Step 2: Identify Gaps

Determine what combinations are **missing** or **underrepresented**:

- Are all traders aggressive? Create a conservative one.
- All focused on BTC? Create an altcoin specialist.
- All using technical analysis? Create a fundamental analyst.
- All short-term? Create a long-term position trader.
- All discretionary? Create a systematic algorithmic trader.

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

## Example Diversity Matrix

When designing traders, vary across these axes:

| Axis | Options |
|------|---------|
| **Risk** | Conservative, Moderate, Aggressive, Very Aggressive |
| **Style** | Day Trading, Swing Trading, Position Trading, Scalping, HFT, Market Making |
| **Focus** | Spot, Futures, Perpetuals, Options, Arbitrage |
| **Asset** | BTC-only, ETH-centric, Altcoins, DeFi, Stablecoins, Diversified |
| **Analysis** | Pure Technical, Fundamental, Sentiment, On-chain, Hybrid, Quant |
| **Timeframe** | Sub-minute, 1m-15m, 1h-4h, Daily, Weekly |
| **Decision** | Discretionary, Systematic, Algorithmic, Copy Trading |
| **Experience** | Retail Beginner, Retail Experienced, Prop Trader, Institutional, Quant |

## Final Instructions

When the user invokes `/newtrader`:

1. **ALWAYS** read all existing `profile.md` files first (in subdirectories)
2. **ALWAYS** analyze what's missing or underrepresented
3. **ALWAYS** create someone distinctly different
4. **NEVER** skip the diversity check
5. **Create exactly ONE trader** unless explicitly told to create more
6. **Use the NUMERIC ID** provided in the instructions (e.g., 1, 2, 3, etc.)
7. **Create a folder** `<TraderName>_<numeric_id>/` with `profile.md` inside
   - Example: `BitcoinMaximalist_1/profile.md`, `QuantumTrader_2/profile.md`, etc.
8. **ONLY select trading pairs from the provided list** (mainstream, high-volume pairs like BTCUSDT, ETHUSDT, etc.)

Your goal is to build a diverse community of traders, each with their own unique approach to the cryptocurrency markets.
