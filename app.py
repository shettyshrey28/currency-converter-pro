"""
Currency Converter Pro
Features:
- Live exchange rates from Frankfurter API
- TTL caching to reduce repeated API calls
- SQLite storage for historical rates
- Historical trend chart and simple linear-regression forecast
- Streamlit web interface
"""

from datetime import date, timedelta
from pathlib import Path
import sqlite3

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
import streamlit as st
from sklearn.linear_model import LinearRegression

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "exchange_rates.db"
API_BASE = "https://api.frankfurter.app"
SUPPORTED_CURRENCIES = [
    "AUD", "BGN", "BRL", "CAD", "CHF", "CNY", "CZK", "DKK", "EUR", "GBP",
    "HKD", "HUF", "IDR", "ILS", "INR", "ISK", "JPY", "KRW", "MXN", "MYR",
    "NOK", "NZD", "PHP", "PLN", "RON", "SEK", "SGD", "THB", "TRY", "USD", "ZAR"
]


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS exchange_rates (
                rate_date TEXT NOT NULL,
                base_currency TEXT NOT NULL,
                target_currency TEXT NOT NULL,
                rate REAL NOT NULL,
                PRIMARY KEY (rate_date, base_currency, target_currency)
            )
        """)
        conn.commit()


def store_rates(base: str, target: str, rates: dict):
    rows = [(str(d), base, target, float(rate)) for d, rate in rates.items()]
    if not rows:
        return
    with sqlite3.connect(DB_PATH) as conn:
        conn.executemany("""
            INSERT OR REPLACE INTO exchange_rates
            (rate_date, base_currency, target_currency, rate)
            VALUES (?, ?, ?, ?)
        """, rows)
        conn.commit()


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_latest_rate(base: str, target: str):
    """Cache latest rate for one hour; same-currency conversion is always 1."""
    if base == target:
        return {"date": date.today().isoformat(), "rate": 1.0}
    url = f"{API_BASE}/latest"
    try:
        response = requests.get(url, params={"from": base, "to": target}, timeout=10)
        response.raise_for_status()
        payload = response.json()
        rate_date = payload.get("date")
        rate = payload.get("rates", {}).get(target)
        if rate is None:
            raise ValueError("The API did not return a rate for this currency pair.")
        store_rates(base, target, {rate_date: rate})
        return {"date": rate_date, "rate": float(rate)}
    except (requests.RequestException, ValueError, KeyError) as exc:
        raise RuntimeError(
            "Could not retrieve the exchange rate. Check your internet connection "
            "and currency selections, then try again."
        ) from exc


@st.cache_data(ttl=21600, show_spinner=False)
def fetch_historical_rates(base: str, target: str, start_date: date, end_date: date):
    """Fetch a date range, cache it for six hours, and persist it to SQLite."""
    if base == target:
        days = pd.date_range(start=start_date, end=end_date, freq="D")
        return pd.DataFrame({"date": days, "rate": 1.0})
    url = f"{API_BASE}/{start_date.isoformat()}..{end_date.isoformat()}"
    try:
        response = requests.get(
            url, params={"from": base, "to": target}, timeout=20
        )
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("rates", {})
        flat = {
            day: values[target]
            for day, values in rows.items()
            if target in values
        }
        if flat:
            store_rates(base, target, flat)
        df = pd.DataFrame(
            [{"date": pd.to_datetime(day), "rate": float(rate)}
             for day, rate in flat.items()]
        )
        if df.empty:
            # Use locally stored data if the API returned no observations.
            with sqlite3.connect(DB_PATH) as conn:
                df = pd.read_sql_query(
                    """SELECT rate_date AS date, rate FROM exchange_rates
                       WHERE base_currency = ? AND target_currency = ?
                       AND rate_date BETWEEN ? AND ? ORDER BY rate_date""",
                    conn,
                    params=(base, target, start_date.isoformat(), end_date.isoformat()),
                )
            if not df.empty:
                df["date"] = pd.to_datetime(df["date"])
        return df.sort_values("date") if not df.empty else df
    except requests.RequestException as exc:
        with sqlite3.connect(DB_PATH) as conn:
            df = pd.read_sql_query(
                """SELECT rate_date AS date, rate FROM exchange_rates
                   WHERE base_currency = ? AND target_currency = ?
                   AND rate_date BETWEEN ? AND ? ORDER BY rate_date""",
                conn,
                params=(base, target, start_date.isoformat(), end_date.isoformat()),
            )
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
            return df
        raise RuntimeError(
            "Could not load historical rates, and no saved history is available yet."
        ) from exc


def forecast_rates(history: pd.DataFrame, days_ahead: int):
    """Simple linear-regression trend estimate, not financial advice."""
    clean = history[["date", "rate"]].dropna().sort_values("date").copy()
    if len(clean) < 3:
        raise ValueError("At least 3 historical observations are needed to forecast.")
    clean["day_number"] = (
        clean["date"] - clean["date"].min()
    ).dt.days
    model = LinearRegression()
    model.fit(clean[["day_number"]], clean["rate"])
    last_day = int(clean["day_number"].max())
    future_days = np.arange(last_day + 1, last_day + days_ahead + 1)
    predictions = model.predict(future_days.reshape(-1, 1))
    future_dates = clean["date"].max() + pd.to_timedelta(
        future_days - last_day, unit="D"
    )
    return pd.DataFrame({"date": future_dates, "rate": predictions})


st.set_page_config(
    page_title="Currency Converter Pro",
    page_icon="💱",
    layout="wide",
)
init_db()

st.title("💱 Currency Converter Pro")
st.caption("Live conversion • Cached rates • Historical analytics • Experimental forecasting")

with st.sidebar:
    st.header("Conversion")
    base = st.selectbox("From currency", SUPPORTED_CURRENCIES, index=SUPPORTED_CURRENCIES.index("USD"))
    target = st.selectbox("To currency", SUPPORTED_CURRENCIES, index=SUPPORTED_CURRENCIES.index("INR"))
    amount = st.number_input("Amount", min_value=0.0, value=100.0, step=10.0, format="%.2f")
    st.caption("Rates are provided by the Frankfurter API. Rates may be delayed and are not trading quotes.")

left, right = st.columns([1, 1])
with left:
    st.subheader("Conversion result")
    try:
        current = fetch_latest_rate(base, target)
        converted = amount * current["rate"]
        st.metric(
            label=f"{amount:,.2f} {base} in {target}",
            value=f"{converted:,.4f} {target}",
            help=f"Rate: 1 {base} = {current['rate']:.6f} {target}",
        )
        st.caption(
            f"Rate date: {current['date']} · 1 {base} = "
            f"{current['rate']:.6f} {target} · Cache TTL: 1 hour"
        )
    except RuntimeError as err:
        st.error(str(err))

with right:
    st.subheader("Quick details")
    st.write(f"**Currency pair:** {base} → {target}")
    st.write(f"**Amount:** {amount:,.2f} {base}")
    st.write("**Storage:** SQLite local database")
    st.write("**Caching:** Streamlit TTL cache")

st.divider()
st.header("Historical trends & forecast")
default_start = date.today() - timedelta(days=365)
date_col1, date_col2, date_col3 = st.columns([1, 1, 1])
with date_col1:
    start_date = st.date_input("Start date", value=default_start, max_value=date.today())
with date_col2:
    end_date = st.date_input("End date", value=date.today(), min_value=start_date, max_value=date.today())
with date_col3:
    forecast_days = st.selectbox("Forecast horizon", [7, 14, 30], index=1)

if start_date > end_date:
    st.warning("Start date must be on or before end date.")
else:
    try:
        with st.spinner("Loading historical exchange rates..."):
            history = fetch_historical_rates(base, target, start_date, end_date)
        if history.empty:
            st.info("No historical observations were returned for this range. Try another date range.")
        else:
            history = history.dropna().sort_values("date")
            latest_rate = float(history.iloc[-1]["rate"])
            first_rate = float(history.iloc[0]["rate"])
            change = latest_rate - first_rate
            pct_change = (change / first_rate * 100) if first_rate else 0.0

            m1, m2, m3 = st.columns(3)
            m1.metric("Observations", f"{len(history):,}")
            m2.metric("First rate", f"{first_rate:.6f}")
            m3.metric("Change over period", f"{pct_change:+.2f}%", delta=f"{change:+.6f}")

            forecast = None
            try:
                forecast = forecast_rates(history, int(forecast_days))
                st.caption(
                    f"Linear-regression trend estimate {forecast_days} days ahead: "
                    f"{forecast.iloc[-1]['rate']:.6f} {target} per {base}. "
                    "This is a simple educational model, not a reliable prediction of market prices."
                )
            except ValueError as err:
                st.info(str(err))

            fig, ax = plt.subplots(figsize=(11, 4.5))
            ax.plot(history["date"], history["rate"], label="Historical rate", linewidth=2)
            if forecast is not None:
                ax.plot(
                    forecast["date"], forecast["rate"],
                    linestyle="--", label="Linear-regression estimate"
                )
                ax.axvline(history["date"].max(), linestyle=":", linewidth=1)
            ax.set_title(f"{base} to {target}: exchange-rate trend")
            ax.set_xlabel("Date")
            ax.set_ylabel(f"{target} per 1 {base}")
            ax.grid(True, alpha=0.25)
            ax.legend()
            fig.tight_layout()
            st.pyplot(fig, use_container_width=True)
            plt.close(fig)

            with st.expander("View historical data"):
                st.dataframe(history.assign(date=history["date"].dt.strftime("%Y-%m-%d")),
                             use_container_width=True, hide_index=True)
                csv = history.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "Download historical data as CSV",
                    data=csv,
                    file_name=f"{base}_{target}_history.csv",
                    mime="text/csv",
                )
    except RuntimeError as err:
        st.error(str(err))

st.divider()
st.caption(
    "Educational project. Exchange rates can be delayed; forecasts are trend extrapolations "
    "and should not be used as financial advice."
)
