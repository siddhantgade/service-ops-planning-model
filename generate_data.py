"""Generate SIMULATED weekly demand data for a financial services customer operations team.

All data is synthetic. Volumes, seasonality and staffing levels are illustrative
assumptions, not taken from any real organisation.

Columns
-------
week_start        Monday of the week
calls             inbound telephony contacts (BAU)
cases_bau         back-office cases received (BAU): transfers, account changes, document processing
cases_change      extra back-office cases caused by a change project (system migration campaign)
cases_outsourced  cases handled by the outsourced provider (share of all cases)
fte_available     in-house FTE available to take work that week
"""
import numpy as np
import pandas as pd

SEED = 42
N_WEEKS = 156                      # three years of weekly history
END_WEEK = pd.Timestamp("2026-09-28")

CALLS_BASE = 4200                  # average BAU calls per week
CASES_BASE = 2600                  # average BAU cases per week
TREND_PER_WEEK = 0.0006            # about 3% growth a year
OUTSOURCED_SHARE = 0.25            # share of all cases routed to the provider

# Calls: tax-year-end (Mar/Apr) and January are busier, summer is quieter
CALL_MONTH = {1: 1.06, 2: 1.00, 3: 1.10, 4: 1.12, 5: 1.02, 6: 0.97,
              7: 0.92, 8: 0.90, 9: 1.00, 10: 1.03, 11: 1.04, 12: 0.98}
# Cases peak harder at tax-year-end because transfers and withdrawals cluster there
CASE_MONTH = {1: 1.05, 2: 0.98, 3: 1.22, 4: 1.28, 5: 1.00, 6: 0.95,
              7: 0.90, 8: 0.88, 9: 1.00, 10: 1.02, 11: 1.03, 12: 0.97}
MONTH_END_UPLIFT = 1.06            # week containing the last working day of the month
CHRISTMAS_DIP = 0.70               # bank-holiday week at year end


def build() -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    weeks = pd.date_range(end=END_WEEK, periods=N_WEEKS, freq="W-MON")
    t = np.arange(N_WEEKS)

    mid_week = weeks + pd.Timedelta(days=3)               # Thursday decides the month
    month = mid_week.month.to_numpy()
    month_end = (mid_week + pd.Timedelta(days=7)).month.to_numpy() != month
    xmas = ((weeks.month == 12) & (weeks.day >= 24)) | ((weeks.month == 12) & (weeks.day + 6 > 31))

    trend = 1 + TREND_PER_WEEK * t
    month_end_f = np.where(month_end, MONTH_END_UPLIFT, 1.0)
    xmas_f = np.where(xmas, CHRISTMAS_DIP, 1.0)

    calls = (CALLS_BASE * trend * np.array([CALL_MONTH[m] for m in month])
             * month_end_f * xmas_f * rng.lognormal(0, 0.04, N_WEEKS))
    cases_bau = (CASES_BASE * trend * np.array([CASE_MONTH[m] for m in month])
                 * month_end_f * xmas_f * rng.lognormal(0, 0.05, N_WEEKS))

    # Change project in history: 8-week migration campaign with a ramp up and down
    cases_change = np.zeros(N_WEEKS)
    start = N_WEEKS - 40
    ramp = np.array([0.4, 0.8, 1.0, 1.0, 1.0, 1.0, 0.7, 0.3])
    cases_change[start:start + 8] = 350 * ramp * rng.lognormal(0, 0.05, 8)

    total_cases = cases_bau + cases_change
    outsourced = total_cases * np.clip(rng.normal(OUTSOURCED_SHARE, 0.015, N_WEEKS), 0.2, 0.3)

    # In-house FTE: steady team with two recruitment steps over the three years
    fte = np.full(N_WEEKS, 58.0)
    fte[52:] += 3
    fte[104:] += 3
    fte = fte + rng.normal(0, 0.6, N_WEEKS)

    return pd.DataFrame({
        "week_start": weeks.date,
        "calls": calls.round().astype(int),
        "cases_bau": cases_bau.round().astype(int),
        "cases_change": cases_change.round().astype(int),
        "cases_outsourced": outsourced.round().astype(int),
        "fte_available": fte.round(1),
    })


if __name__ == "__main__":
    df = build()
    df.to_csv("data/service_ops_demand.csv", index=False)
    print(f"Wrote data/service_ops_demand.csv: {len(df)} weeks, "
          f"{df.week_start.iloc[0]} to {df.week_start.iloc[-1]}")
