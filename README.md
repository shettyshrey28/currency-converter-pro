# Currency Converter Pro

A web-based currency converter with live reference rates, caching, historical analytics, and a simple forecasting demonstration.

## Features
- Latest exchange rates from the Frankfurter API
- One-hour TTL cache for latest rates and six-hour cache for historical responses
- SQLite persistence for retrieved historical rates
- Historical rate chart with date-range controls
- Simple linear-regression trend estimate for 7, 14, or 30 days
- CSV export of historical observations
- Input validation and user-friendly API error messages

## Run locally

If you want to run or modify the project on your own computer:

1. Install Python 3.10 or newer.
2. Open a terminal in the project folder.
3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Start the application:

   ```bash
   streamlit run app.py
   ```

Streamlit will display a local URL, usually `http://localhost:8501`. This address is for running the app on your own computer; it is not the public website link.

## Using the hosted app

If you are viewing this repository because you want to use the application, you do **not** need to deploy it yourself. Open the project's published web-app link (add it here after deployment), and use the converter in your browser.

> https://currency-converter-pro-9htkqwsdazdxcpnphveejj.streamlit.app

## Project structure

```text
currency-converter-pro/
├── app.py
├── requirements.txt
├── README.md
└── render.yaml
```

The `exchange_rates.db` SQLite database is created automatically when the app runs. It is not required in the repository.

## Technical notes
- Exchange rates are supplied by the Frankfurter API. They are reference rates, not guaranteed real-time trading quotes.
- The forecast is a basic linear-regression trend extrapolation for educational purposes. It is not financial advice or a reliable prediction of future market prices.
- Streamlit's cache is held in the running app instance. On some hosting platforms, local SQLite data may be lost when an instance is replaced or redeployed. Persistent storage is needed for long-term retention.
