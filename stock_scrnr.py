import requests
from bs4 import BeautifulSoup
import yfinance as yf


# ─────────────────────────────────────────────
#  DATA FETCHING
# ─────────────────────────────────────────────

def fetch_finviz(ticker: str) -> dict:
    url = f"https://finviz.com/quote.ashx?t={ticker}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
    except Exception as e:
        print(f"[Finviz] Request failed: {e}")
        return {}

    soup = BeautifulSoup(res.text, "html.parser")
    table = soup.find("table", class_="snapshot-table2")
    if not table:
        print("[Finviz] Could not find data table.")
        return {}

    raw = {}
    cells = table.find_all("td")
    for i in range(0, len(cells) - 1, 2):
        raw[cells[i].get_text(strip=True)] = cells[i + 1].get_text(strip=True)
    return raw


def fetch_yfinance(ticker: str) -> dict:
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        financials = stock.financials

        op_margin = None
        try:
            op_income = financials.loc["Operating Income"].iloc[0]
            revenue   = financials.loc["Total Revenue"].iloc[0]
            op_margin = op_income / revenue if revenue else None
        except Exception:
            pass

        fcf_yield = None
        try:
            fcf = info.get("freeCashflow")
            mkt = info.get("marketCap")
            if fcf and mkt:
                fcf_yield = fcf / mkt
        except Exception:
            pass

        return {
            "roe":             info.get("returnOnEquity"),
            "revenue_growth":  info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "beta":            info.get("beta"),
            "forward_pe":      info.get("forwardPE"),
            "price_to_book":   info.get("priceToBook"),
            "peg_ratio":       info.get("pegRatio"),
            "short_ratio":     info.get("shortRatio"),
            "op_margin":       op_margin,
            "fcf_yield":       fcf_yield,
            "sector":          info.get("sector", "Unknown"),
            "name":            info.get("longName", ticker.upper()),
        }
    except Exception as e:
        print(f"[yfinance] Failed: {e}")
        return {}


def parse_finviz_value(s: str):
    """Convert Finviz string values to floats."""
    if not s or s == "-":
        return None
    try:
        s = s.strip()
        if s.endswith("%"):
            return float(s[:-1]) / 100
        multipliers = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}
        if s[-1] in multipliers:
            return float(s[:-1].replace(",", "")) * multipliers[s[-1]]
        return float(s.replace(",", ""))
    except Exception:
        return None


def gather_metrics(ticker: str) -> dict:
    raw_fv = fetch_finviz(ticker)
    yf_data = fetch_yfinance(ticker)

    fv = {k: parse_finviz_value(v) for k, v in raw_fv.items()}

    return {
        # Identification
        "ticker": ticker.upper(),
        "name":   yf_data.get("name", ticker.upper()),
        "sector": yf_data.get("sector", "Unknown"),

        # Valuation
        "pe":           fv.get("P/E") or yf_data.get("forward_pe"),
        "forward_pe":   yf_data.get("forward_pe"),
        "price_to_book":yf_data.get("price_to_book"),
        "peg_ratio":    yf_data.get("peg_ratio"),
        "fcf_yield":    yf_data.get("fcf_yield"),

        # Profitability
        "roi":           fv.get("ROI"),
        "roe":           yf_data.get("roe"),
        "gross_margin":  fv.get("Gross Margin"),
        "op_margin":     yf_data.get("op_margin") or fv.get("Operating Margin"),

        # Momentum
        "rsi":           fv.get("RSI (14)"),
        "beta":          yf_data.get("beta"),

        # Financial health
        "debt_to_equity": fv.get("Debt/Eq"),
        "revenue_growth": yf_data.get("revenue_growth"),
        "earnings_growth":yf_data.get("earnings_growth"),
        "short_ratio":    yf_data.get("short_ratio"),
    }


# ─────────────────────────────────────────────
#  SCORING ENGINE  (each function returns 0–100)
# ─────────────────────────────────────────────

def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def score_valuation(m: dict) -> tuple[float, list[str]]:
    points, notes = 0.0, []
    count = 0

    # P/E (trailing or forward)
    pe = m.get("pe")
    if pe is not None and pe > 0:
        count += 1
        if pe <= 10:
            pts = 40; tag = "Very low P/E — possible value trap or undervalued"
        elif pe <= 20:
            pts = 80; tag = f"P/E {pe:.1f} — fairly valued"
        elif pe <= 30:
            pts = 60; tag = f"P/E {pe:.1f} — moderate premium"
        elif pe <= 50:
            pts = 35; tag = f"P/E {pe:.1f} — high growth priced in"
        else:
            pts = 15; tag = f"P/E {pe:.1f} — speculative / very expensive"
        points += pts; notes.append(f"  P/E: {tag}")

    # FCF Yield
    fcf = m.get("fcf_yield")
    if fcf is not None:
        count += 1
        pct = fcf * 100
        if pct > 10:
            pts = 100; tag = f"{pct:.1f}% — very undervalued"
        elif pct >= 5:
            pts = 75;  tag = f"{pct:.1f}% — healthy cash generation"
        elif pct >= 2:
            pts = 45;  tag = f"{pct:.1f}% — below average"
        else:
            pts = 15;  tag = f"{pct:.1f}% — overvalued or reinvesting heavily"
        points += pts; notes.append(f"  FCF yield: {tag}")

    # Price-to-book
    pb = m.get("price_to_book")
    if pb is not None and pb > 0:
        count += 1
        if pb <= 1:
            pts = 90; tag = f"P/B {pb:.1f} — trading near/below book"
        elif pb <= 3:
            pts = 70; tag = f"P/B {pb:.1f} — reasonable"
        elif pb <= 6:
            pts = 45; tag = f"P/B {pb:.1f} — elevated"
        else:
            pts = 20; tag = f"P/B {pb:.1f} — very expensive vs assets"
        points += pts; notes.append(f"  Price/Book: {tag}")

    # PEG ratio
    peg = m.get("peg_ratio")
    if peg is not None and peg > 0:
        count += 1
        if peg < 1:
            pts = 90; tag = f"PEG {peg:.2f} — undervalued relative to growth"
        elif peg <= 1.5:
            pts = 70; tag = f"PEG {peg:.2f} — fairly valued for growth"
        elif peg <= 2.5:
            pts = 45; tag = f"PEG {peg:.2f} — slightly stretched"
        else:
            pts = 20; tag = f"PEG {peg:.2f} — expensive for growth rate"
        points += pts; notes.append(f"  PEG: {tag}")

    score = (points / count) if count else None
    return score, notes


def score_profitability(m: dict) -> tuple[float, list[str]]:
    points, notes = 0.0, []
    count = 0

    # ROI
    roi = m.get("roi")
    if roi is not None:
        count += 1
        roi_pct = roi * 100 if abs(roi) < 1 else roi
        if roi_pct > 20:
            pts = 100; tag = f"{roi_pct:.1f}% — exceptional"
        elif roi_pct > 15:
            pts = 85;  tag = f"{roi_pct:.1f}% — excellent"
        elif roi_pct > 10:
            pts = 70;  tag = f"{roi_pct:.1f}% — good"
        elif roi_pct > 5:
            pts = 50;  tag = f"{roi_pct:.1f}% — moderate"
        elif roi_pct > 0:
            pts = 25;  tag = f"{roi_pct:.1f}% — weak"
        else:
            pts = 0;   tag = f"{roi_pct:.1f}% — negative ⚠"
        points += pts; notes.append(f"  ROI: {tag}")

    # ROE
    roe = m.get("roe")
    if roe is not None:
        count += 1
        roe_pct = roe * 100
        if roe_pct > 20:
            pts = 100; tag = f"{roe_pct:.1f}% — outstanding"
        elif roe_pct > 15:
            pts = 80;  tag = f"{roe_pct:.1f}% — strong"
        elif roe_pct > 10:
            pts = 60;  tag = f"{roe_pct:.1f}% — decent"
        elif roe_pct > 0:
            pts = 30;  tag = f"{roe_pct:.1f}% — low"
        else:
            pts = 0;   tag = f"{roe_pct:.1f}% — negative ⚠"
        points += pts; notes.append(f"  ROE: {tag}")

    # Operating margin
    op_m = m.get("op_margin")
    if op_m is not None:
        count += 1
        pct = op_m * 100 if abs(op_m) < 1 else op_m
        if pct > 25:
            pts = 100; tag = f"{pct:.1f}% — exceptional"
        elif pct > 15:
            pts = 80;  tag = f"{pct:.1f}% — healthy"
        elif pct > 8:
            pts = 60;  tag = f"{pct:.1f}% — acceptable"
        elif pct > 0:
            pts = 30;  tag = f"{pct:.1f}% — thin"
        else:
            pts = 0;   tag = f"{pct:.1f}% — operating loss ⚠"
        points += pts; notes.append(f"  Operating margin: {tag}")

    # Gross margin
    gm = m.get("gross_margin")
    if gm is not None:
        count += 1
        pct = gm * 100 if abs(gm) < 1 else gm
        if pct > 60:
            pts = 100; tag = f"{pct:.1f}% — software/pharma-tier"
        elif pct > 40:
            pts = 80;  tag = f"{pct:.1f}% — strong"
        elif pct > 20:
            pts = 55;  tag = f"{pct:.1f}% — moderate"
        else:
            pts = 25;  tag = f"{pct:.1f}% — low (may be capital-intensive)"
        points += pts; notes.append(f"  Gross margin: {tag}")

    score = (points / count) if count else None
    return score, notes


def score_momentum(m: dict) -> tuple[float, list[str]]:
    points, notes = 0.0, []
    count = 0

    # RSI
    rsi = m.get("rsi")
    if rsi is not None:
        count += 1
        if rsi > 80:
            pts = 20; tag = f"{rsi:.1f} — extremely overbought ⚠"
        elif rsi > 70:
            pts = 40; tag = f"{rsi:.1f} — overbought, risk of pullback"
        elif rsi > 55:
            pts = 85; tag = f"{rsi:.1f} — bullish uptrend"
        elif rsi > 45:
            pts = 60; tag = f"{rsi:.1f} — neutral zone"
        elif rsi > 35:
            pts = 40; tag = f"{rsi:.1f} — bearish/weakening"
        elif rsi > 20:
            pts = 55; tag = f"{rsi:.1f} — oversold, potential bounce"
        else:
            pts = 35; tag = f"{rsi:.1f} — extremely oversold"
        points += pts; notes.append(f"  RSI: {tag}")

    # Beta (risk-adjusted momentum)
    beta = m.get("beta")
    if beta is not None:
        count += 1
        if 0.8 <= beta <= 1.2:
            pts = 75; tag = f"{beta:.2f} — market-correlated, stable"
        elif beta < 0.8:
            pts = 65; tag = f"{beta:.2f} — low volatility / defensive"
        elif beta <= 1.5:
            pts = 55; tag = f"{beta:.2f} — moderately volatile"
        else:
            pts = 30; tag = f"{beta:.2f} — high volatility ⚠"
        points += pts; notes.append(f"  Beta: {tag}")

    score = (points / count) if count else None
    return score, notes


def score_health(m: dict) -> tuple[float, list[str]]:
    points, notes = 0.0, []
    count = 0

    # Debt/Equity
    de = m.get("debt_to_equity")
    if de is not None:
        count += 1
        if de < 0.3:
            pts = 100; tag = f"{de:.2f} — very low leverage"
        elif de < 0.7:
            pts = 80;  tag = f"{de:.2f} — healthy"
        elif de < 1.5:
            pts = 55;  tag = f"{de:.2f} — moderate leverage"
        elif de < 3:
            pts = 30;  tag = f"{de:.2f} — highly leveraged ⚠"
        else:
            pts = 10;  tag = f"{de:.2f} — dangerous debt load ⚠"
        points += pts; notes.append(f"  Debt/Equity: {tag}")

    # Revenue growth
    rg = m.get("revenue_growth")
    if rg is not None:
        count += 1
        pct = rg * 100
        if pct > 25:
            pts = 100; tag = f"{pct:.1f}% — high growth"
        elif pct > 10:
            pts = 80;  tag = f"{pct:.1f}% — solid growth"
        elif pct > 0:
            pts = 55;  tag = f"{pct:.1f}% — slow growth"
        else:
            pts = 15;  tag = f"{pct:.1f}% — declining revenue ⚠"
        points += pts; notes.append(f"  Revenue growth: {tag}")

    # Earnings growth
    eg = m.get("earnings_growth")
    if eg is not None:
        count += 1
        pct = eg * 100
        if pct > 20:
            pts = 100; tag = f"{pct:.1f}% — strong earnings growth"
        elif pct > 5:
            pts = 75;  tag = f"{pct:.1f}% — healthy"
        elif pct >= 0:
            pts = 45;  tag = f"{pct:.1f}% — flat earnings"
        else:
            pts = 10;  tag = f"{pct:.1f}% — shrinking earnings ⚠"
        points += pts; notes.append(f"  Earnings growth: {tag}")

    # Short ratio (high short interest = bearish signal)
    sr = m.get("short_ratio")
    if sr is not None:
        count += 1
        if sr < 2:
            pts = 85; tag = f"{sr:.1f} days — low short interest"
        elif sr < 5:
            pts = 65; tag = f"{sr:.1f} days — moderate"
        elif sr < 10:
            pts = 35; tag = f"{sr:.1f} days — elevated short interest ⚠"
        else:
            pts = 10; tag = f"{sr:.1f} days — heavily shorted ⚠"
        points += pts; notes.append(f"  Short ratio: {tag}")

    score = (points / count) if count else None
    return score, notes


# ─────────────────────────────────────────────
#  COMPOSITE SCORE + VERDICT
# ─────────────────────────────────────────────

WEIGHTS = {
    "valuation":    0.35,
    "profitability":0.30,
    "momentum":     0.20,
    "health":       0.15,
}

BAR_WIDTH = 30  # characters wide for the bar chart


def get_verdict(score: float) -> str:
    if score >= 85: return "⭐ STRONG BUY"
    if score >= 70: return "✅ BUY"
    if score >= 55: return "➡️  NEUTRAL / HOLD"
    if score >= 40: return "⚠️  WEAK — proceed with caution"
    return "🚫 AVOID"


def score_color(score: float) -> str:
    """Return an ANSI color code based on score."""
    if score >= 70: return "\033[92m"   # green
    if score >= 55: return "\033[93m"   # yellow
    if score >= 40: return "\033[33m"   # dark yellow
    return "\033[91m"                   # red

RESET = "\033[0m"
BOLD  = "\033[1m"


def render_bar(score: float, width: int = BAR_WIDTH) -> str:
    """Render a filled bar like  ████████████░░░░░░  72"""
    if score is None:
        return "  " + "─" * width + "  N/A"
    filled = round((score / 100) * width)
    empty  = width - filled
    color  = score_color(score)
    bar    = f"{color}{'█' * filled}{RESET}{'░' * empty}"
    return f"  {bar}  {color}{BOLD}{score:>3.0f}{RESET}"


def render_chart(category_scores: dict, composite: float) -> None:
    """Print a terminal bar chart of category scores + composite."""
    labels = {
        "valuation":     f"Valuation     (35%)",
        "profitability": f"Profitability (30%)",
        "momentum":      f"Momentum      (20%)",
        "health":        f"Health        (15%)",
    }

    print(f"\n  {'─'*52}")
    print(f"  {BOLD}SCORE BREAKDOWN{RESET}")
    print(f"  {'─'*52}")

    for key, label in labels.items():
        score = category_scores.get(key)
        bar   = render_bar(score)
        print(f"  {label:<22}{bar}")

    print(f"  {'─'*52}")

    # Composite bar — slightly wider to stand out
    comp_filled = round((composite / 100) * BAR_WIDTH)
    comp_empty  = BAR_WIDTH - comp_filled
    comp_color  = score_color(composite)
    comp_bar    = f"{comp_color}{'█' * comp_filled}{RESET}{'░' * comp_empty}"
    print(f"  {'COMPOSITE':>22}  {comp_bar}  {comp_color}{BOLD}{composite:>3.0f}{RESET}")

    # Score band legend
    print(f"\n  {'─'*52}")
    legend = (
        f"  \033[91m■\033[0m 0–39 Avoid  "
        f"\033[33m■\033[0m 40–54 Weak  "
        f"\033[93m■\033[0m 55–69 Neutral  "
        f"\033[92m■\033[0m 70–84 Buy  "
        f"\033[92m■\033[0m 85+ Strong buy"
    )
    print(legend)


def analyze(ticker: str) -> None:
    print(f"\n{'═'*52}")
    metrics = gather_metrics(ticker)
    print(f"  {BOLD}{metrics['name']}{RESET}  ({metrics['ticker']})  |  Sector: {metrics['sector']}")
    print(f"{'═'*52}")

    v_score, v_notes = score_valuation(metrics)
    p_score, p_notes = score_profitability(metrics)
    m_score, m_notes = score_momentum(metrics)
    h_score, h_notes = score_health(metrics)

    category_scores = {
        "valuation":     v_score,
        "profitability": p_score,
        "momentum":      m_score,
        "health":        h_score,
    }

    # Print category breakdowns with notes
    total_weight = 0
    composite = 0.0
    for label, cat_key, notes in [
        ("Valuation",       "valuation",     v_notes),
        ("Profitability",   "profitability", p_notes),
        ("Momentum",        "momentum",      m_notes),
        ("Financial health","health",        h_notes),
    ]:
        score  = category_scores[cat_key]
        weight = WEIGHTS[cat_key]
        score_str = f"{score:.0f}/100" if score is not None else "N/A"
        print(f"\n  {BOLD}{label}{RESET} ({int(weight*100)}% weight) ── {score_str}")
        for note in notes:
            print(f"   {note}")
        if score is not None:
            composite += score * weight
            total_weight += weight

    # Renormalize if some categories had no data
    if 0 < total_weight < 1:
        composite = composite / total_weight

    # Chart
    render_chart(category_scores, composite)

    # Final verdict
    print(f"\n  {BOLD}COMPOSITE SCORE:{RESET}  {composite:.0f} / 100")
    print(f"  {BOLD}VERDICT:{RESET}          {get_verdict(composite)}")
    print(f"{'═'*52}\n")


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    raw = input("Enter ticker(s), comma-separated: ").strip()
    tickers = [t.strip().upper() for t in raw.split(",") if t.strip()]
    for t in tickers:
        analyze(t)