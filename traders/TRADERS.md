# Trader Generation Guide

## Core Requirements

**Perpetual Futures Only** - All traders MUST support:
- Both LONG and SHORT positions
- Leverage usage (minimum 1x)
- Funding rates, liquidation management

Traders who only go long or avoid leverage/futures are INVALID.

## Objective

Generate unique, diverse cryptocurrency trading strategy profiles as markdown files. Each trader must be **distinctly different** from existing ones.

## Diversity Check

The existing traders summary is provided in your instructions - use it to ensure diversity by analyzing:
- Trading styles
- Risk tolerance
- Asset preferences
- Timeframe focus

## Trader Profile Template

```markdown
# <Trader Name>

**Trader ID:** `<numeric_id>` (e.g., 1, 2, 3)
**Created:** `<date>`
**Diversity Score:** `<estimated_similarity_vs_existing>`

## Identity

- **Name:** `<descriptive>`
- **Experience:** `<intermediate/advanced/expert>`
- **Personality:** `<traits affecting trading>`

## Characteristics

- **Risk Tolerance:** `<conservative/moderate/aggressive/very_aggressive>`
- **Capital Allocation:** `<percentage per trade>`
- **Max Drawdown:** `<maximum loss>`
- **Position Size:** `<small/medium/large>`
- **Leverage:** `<1-2x / 2-5x / 5-10x / 10x+>` (must use leverage)
- **Short Selling:** `<always / when_signals / rarely / hedging>` (must be willing)
- **Directional Bias:** `<long_biased / short_biased / neutral / opportunistic>`

## Trading Style

- **Primary Style:** `<day/swing/position/scalping/HFT/making/arbitrage>`
- **Holding Period:** `<minutes/hours/days/weeks>`
- **Frequency:** `<1-5 / 5-20 / 20+ trades/day>`
- **Market:** `Perpetual Futures` (fixed - never change)

## Strategy

### Entry Conditions
`<Detailed entry rules>`

### Exit Conditions
- **Take Profit:** `<TP strategy>`
- **Stop Loss:** `<SL strategy>`
- **Trailing:** `<method if applicable>`

### Risk Management
- **Position Sizing:** `<formula/approach>`
- **Portfolio Allocation:** `<distribution>`
- **Risk/Reward:** `<minimum R:R>`

### Special Tactics
`<Unique strategies/patterns>`

## Instruments

- **Primary Assets:** `<BTC/ETH/altcoins/etc>`
- **Preferred Pairs:** `<from provided list only>`
- **Avoidance:** `<assets/conditions to avoid>`

## Timeframes

- **Analysis:** `<higher timeframe>`
- **Entry:** `<lower timeframe>`
- **Monitoring:** `<check frequency>`

## Edge & Philosophy

**Trading Edge:** `<market advantage>`

**Market Philosophy:** `<beliefs about markets>`

**Strengths:** `<what trader does well>`

**Psychology:** `<emotional handling>`

## Example Trade

**Setup:** `<conditions>`

**Analysis:** `<reasoning>`

**Entry:** `<price/timing>`

**Exit:** `<price/timing>`

**Result:** `<outcome/lessons>`

## Performance Notes
`<historical data or expectations>`

## Metadata

- **Diversity Tags:** `<keywords>`
- **Similar Traders:** `<none or list>`
- **Generation Prompt:** `<original user prompt>`
```

## Generation Process

1. **Review** existing traders summary from instructions
2. **Identify gaps** in styles, risk, assets, timeframes
3. **Design unique trader** that differs from 80%+ of existing ones
4. **Generate file:**
   - Use provided NUMERIC ID
   - Create folder: `<TraderName>_<id>/`
   - Create file: `profile.md` inside
   - Fill ALL sections
   - Select pairs ONLY from provided list
5. **Validate diversity** - would this trader stand out?

## Quality Guidelines

| Do | Don't |
|----|--------|
| Include strengths AND weaknesses | Create perfect traders |
| Use specific actionable strategies | Use vague platitudes |
| Add personality informing decisions | Copy existing traders |
| Describe clear entry/exit rules | Ignore risk management |
| Ensure internal consistency | Leave placeholders unfilled |
| Support both LONG and SHORT | Create spot-only traders |
| Use leverage (min 1x) | Set leverage to "none" |

## Diversity Axes

| Axis | Options |
|------|---------|
| Risk | Conservative, Moderate, Aggressive, Very Aggressive |
| Style | Day, Swing, Position, Scalping, HFT, Market Making, Arbitrage |
| Direction | Long-Biased, Short-Biased, Neutral, Opportunistic |
| Leverage | 1-2x, 2-5x, 5-10x, 10x+ |
| Asset | BTC-only, ETH-centric, Altcoins, DeFi, Diversified |
| Analysis | Technical, Fundamental, Sentiment, On-chain, Hybrid, Quant |
| Timeframe | Sub-minute, 1m-15m, 1h-4h, Daily, Weekly |
| Decision | Discretionary, Systematic, Algorithmic |

## Execution Checklist

When `/traders -a` is invoked:

1. Review existing traders summary from instructions
2. Analyze missing/underrepresented combinations
3. Create distinctly different trader
4. Use provided NUMERIC ID
5. Create folder `<TraderName>_<id>/` with `profile.md` inside
6. Select pairs ONLY from provided list
7. Ensure LONG + SHORT capability
8. Specify leverage usage (min 1x)
9. Market Focus = Perpetual Futures (never change)
10. Create exactly ONE trader unless told otherwise
