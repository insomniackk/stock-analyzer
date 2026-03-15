# stock-analyzer

Stock Analyzer

A terminal-based stock analysis tool that pulls real-time data from Finviz and yfinance, scores a stock across four fundamental categories, and visualizes the results as a color-coded bar chart — all in one script, no browser needed.

---

Features

- Dual data sources — merges Finviz scraping with yfinance API for maximum metric coverage
- Composite scoring system — each stock is scored 0–100 across four weighted categories
- Color-coded terminal chart — instant visual breakdown of where a stock is strong or weak
- Multi-ticker support — analyze several stocks in one run with comma-separated input
- Graceful data gaps — if a metric is unavailable, scoring renormalizes around what it has

---

Scoring System

Each category scores internally from 0–100, then gets weighted into a final composite score.

| Category | Weight | Metrics |
|---|---|---|
| Valuation | 35% | P/E, FCF Yield, Price/Book, PEG Ratio |
| Profitability | 30% | ROI, ROE, Operating Margin, Gross Margin |
| Momentum | 20% | RSI (14-day), Beta |
| Financial Health | 15% | Debt/Equity, Revenue Growth, Earnings Growth, Short Ratio |

Score Bands

| Score | Verdict |
|---|---|
| 85 – 100 | ⭐ Strong Buy |
| 70 – 84 | ✅ Buy |
| 55 – 69 | ➡️ Neutral / Hold |
| 40 – 54 | ⚠️ Weak |
| 0 – 39 | 🚫 Avoid |

---

Sample Output

```
════════════════════════════════════════════════════
  Apple Inc.  (AAPL)  |  Sector: Technology
════════════════════════════════════════════════════

  Valuation (35% weight) ── 52/100
    P/E: 28.4 — moderate premium
    FCF yield: 3.8% — below average
    Price/Book: 45.2 — very expensive vs assets
    PEG: 2.1 — slightly stretched

  Profitability (30% weight) ── 91/100
    ROI: 32.5% — exceptional
    ROE: 147.2% — outstanding
    Operating margin: 31.5% — exceptional
    Gross margin: 46.2% — strong

  Momentum (20% weight) ── 72/100
    RSI: 58.3 — bullish uptrend
    Beta: 1.24 — moderately volatile

  Financial health (15% weight) ── 68/100
    Debt/Equity: 1.73 — highly leveraged ⚠
    Revenue growth: 4.9% — slow growth
    Earnings growth: 11.2% — healthy
    Short ratio: 1.8 days — low short interest

  ────────────────────────────────────────────────────
  SCORE BREAKDOWN
  ────────────────────────────────────────────────────
  Valuation     (35%)  ████████████████░░░░░░░░░░░░░░   52
  Profitability (30%)  ████████████████████████████░░   91
  Momentum      (20%)  ██████████████████████░░░░░░░░   72
  Health        (15%)  ████████████████████░░░░░░░░░░   68
  ────────────────────────────────────────────────────
  COMPOSITE             ████████████████████░░░░░░░░░░   70

  ■ 0–39 Avoid  ■ 40–54 Weak  ■ 55–69 Neutral  ■ 70–84 Buy  ■ 85+ Strong buy

  COMPOSITE SCORE:  70 / 100
  VERDICT:          ✅ BUY
════════════════════════════════════════════════════
```

---

Installation

```bash
git clone https://github.com/yourusername/stock-analyzer.git
cd stock-analyzer
pip install -r requirements.txt
```

requirements.txt
```
requests
beautifulsoup4
yfinance
```

---

Usage

```bash
python stock_analyzer.py
```

When prompted, enter one or more tickers:

```
Enter ticker(s), comma-separated: AAPL
Enter ticker(s), comma-separated: AAPL, MSFT, NVDA
```

---

Configuration

The category weights are defined at the top of the scoring section and can be adjusted to match your investment style:

```python
WEIGHTS = {
    "valuation":     0.35,
    "profitability": 0.30,
    "momentum":      0.20,
    "health":        0.15,
}
```

> Note: Finviz may rate-limit frequent requests. If you see fetch failures, wait a moment and retry or run fewer tickers per session.

---

Disclaimer

This tool is for informational and educational purposes only. It is not financial advice. Always do your own research before making investment decisions.
