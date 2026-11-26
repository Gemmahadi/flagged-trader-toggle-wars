# FlaggedTrader — Toggle Wars (Track 02: AI Agents & Feature Flags)

DuoTrade's Trader agent, steered live by Flagsmith feature flags. The agent
doesn't have one fixed strategy — it runs whichever strategy the flags say,
and we A/B-test which one actually wins on real market data.

## What it is

- **Analyst Agent** (Lyzr Studio, REST) computes the signal from live
  CoinGecko prices — RSI(14) + SMA200, Adi's backtested rule.
- **Trader Agent** (Lyzr Studio, REST) decides the trade — its risk profile,
  position size and reasoning engine are read from Flagsmith at run time.
- **Experiment**: the same 30 days of real 1h closes replayed through all
  three `trader_strategy` variants. The flags decide the winner, not an
  opinion.

## Flags (project `toggle-wars`)

| Flag | Type | Values |
|---|---|---|
| `trader_strategy` | multivariate | conservative / balanced / aggressive |
| `enable_lyzr_reasoning` | boolean | on / off |
| `risk_per_trade` | remote config | 0.05 / 0.10 / 0.20 |

Strategy table: conservative RSI<25, 5%, uptrend only; balanced RSI<30, 10%,
uptrend only; aggressive RSI<35, 20%, buys the dip outright.

## Run

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in FLAGSMITH_KEY, LYZR_API_KEY, Band keys
python3 run_experiment.py   # replay + dashboard.html
python3 toggle_test.py      # live toggle proof: identities + divergence scan
python3 run_demo.py         # live run: Lyzr reasoning + Band handoff + paper trade
```

## Fresh replay (26 Nov 2026 14:29 WIB, real 30d tape, 721 hourly closes)

| Variant | ETH | BTC |
|---|---|---|
| buy-and-hold | $7,307 (−26.9%) | $7,593 (−24.1%) |
| conservative | $10,000 (0 trades) | $10,000 (0 trades) |
| balanced | $10,000 (0 trades) | $10,000 (0 trades) |
| aggressive | $9,568 (−4.3%, 3 trades) | $9,656 (−3.4%, 3 trades) |

Live flags at run time (mode `flagsmith`): conservative / Lyzr on / risk 0.10.

In this tape the uptrend filter kept the strict variants in cash — capital
preserved while buy-and-hold lost a quarter. The dip-buyer traded and lost
~4%, still beating buy-and-hold. Honest numbers, no cherry-picking.

## Live toggle proof (`toggle_test.py`)

Flagsmith's multivariate flag returns all 3 values live across 12 test
identities (4 aggressive / 4 balanced / 4 conservative). On identical
market data the flag changes the decision: ETH hour 223 (price $2,339.87,
RSI 33.38, SMA200 $2,294.97) → aggressive BUY, balanced HOLD,
conservative HOLD.

## Live run (26 Nov 14:35 WIB)

Flags read live (conservative, Lyzr on, risk 0.10). ETH $1,688.11
(RSI 54.77) HOLD, BTC $60,467.12 (RSI 57.97) HOLD — neutral band, no edge.
Analyst + Trader reasoned via Lyzr (real LLM text) and posted 4 messages
to the Band room; transcript in `data/band_transcript.md`. Portfolio
$10,000, no positions. Demo video: `demo/flagged-trader-demo.mp4`
(20 s, 1280×720, re-rendered with fresh data).

Simulated paper trading only. No real money, no real orders.
Not financial advice.
