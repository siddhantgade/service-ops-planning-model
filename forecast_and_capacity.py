"""Demand forecasting and capacity planning for a SIMULATED customer operations team.

Steps
-----
1. Forecast BAU weekly demand (calls and back-office cases) and test accuracy on a 13-week holdout.
2. Re-fit on all history and forecast the next 13 weeks.
3. Convert demand into workload hours and required FTE, then compare with available FTE.
4. Run three scenarios (base, base + change project, peak + higher absence) and size the gap.
5. Track the outsourced provider's forecast volume against its contracted weekly volume.

All figures come from simulated data and illustrative assumptions (see ASSUMPTIONS).
"""
import json
import math
import warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------- assumptions
ASSUMPTIONS = {
    "holdout_weeks": 13,
    "horizon_weeks": 13,
    "season_length_weeks": 52,
    "aht_call_min": 7,                  # average handling time per call
    "aht_case_min": 22,                 # average handling time per back-office case
    "contracted_hours_per_fte": 37.5,
    "shrinkage": 0.30,                  # holidays, sickness, training, meetings
    "occupancy": 0.85,                  # share of productive time spent on work
    "outsourced_share": 0.25,           # share of all cases routed to the provider
    "provider_weekly_cap_cases": 800,   # contracted weekly volume for the provider
    "overtime_hours_per_fte": 4,        # maximum overtime per FTE per week
    "variance_flag_pct": 10,            # flag weeks where actual differs from forecast by more than this
    "interval_z": 1.28,                 # 80% prediction interval
    # Known staffing movements in forecast weeks (week number: change in available FTE)
    "planned_fte_changes": {5: -2, 9: 3},
    # Scenario inputs
    "change_cases_per_week": 350,       # extra cases from a planned change project
    "change_weeks": [4, 5, 6, 7, 8, 9],
    "change_ramp": [0.4, 0.8, 1.0, 1.0, 0.7, 0.3],
    "peak_weeks": [6, 7, 8, 9, 10],
    "peak_uplift": 0.10,                # extra volume in peak weeks
    "peak_shrinkage": 0.35,             # winter absence in peak weeks
}
A = ASSUMPTIONS


def mape(actual, fc):
    actual, fc = np.asarray(actual, float), np.asarray(fc, float)
    return float(np.mean(np.abs((actual - fc) / actual)) * 100)


def bias(actual, fc):
    actual, fc = np.asarray(actual, float), np.asarray(fc, float)
    return float((np.sum(fc) - np.sum(actual)) / np.sum(actual) * 100)


def seasonal_naive(train: pd.Series, h: int) -> np.ndarray:
    """Same week last year."""
    m = A["season_length_weeks"]
    return np.array([train.iloc[len(train) + i - m] for i in range(h)], float)


def holt_winters(train: pd.Series, h: int) -> np.ndarray:
    model = ExponentialSmoothing(
        train.values.astype(float), trend="add", damped_trend=True, seasonal="mul",
        seasonal_periods=A["season_length_weeks"], initialization_method="estimated",
    ).fit()
    return np.asarray(model.forecast(h))


MODELS = {"Seasonal naive": seasonal_naive, "Holt-Winters": holt_winters}


def backtest(df: pd.DataFrame, col: str):
    h = A["holdout_weeks"]
    train, test = df[col].iloc[:-h], df[col].iloc[-h:]
    rows, fcs = [], {}
    for name, fn in MODELS.items():
        fc = fn(train, h)
        fcs[name] = fc
        rows.append({"series": col, "model": name,
                     "MAPE_pct": round(mape(test, fc), 2),
                     "bias_pct": round(bias(test, fc), 2),
                     "RMSE": round(float(np.sqrt(np.mean((test.values - fc) ** 2))), 1)})
    res = pd.DataFrame(rows)
    best = res.sort_values("MAPE_pct").iloc[0]["model"]
    return res, best, fcs[best], test


def productive_hours(shrinkage=None):
    s = A["shrinkage"] if shrinkage is None else shrinkage
    return A["contracted_hours_per_fte"] * (1 - s) * A["occupancy"]


def capacity_for_scenario(name, calls, cases_bau, change_cases, weeks, available, peak_on):
    rows = []
    for i, wk in enumerate(weeks):
        wknum = i + 1
        uplift = 1 + A["peak_uplift"] if (peak_on and wknum in A["peak_weeks"]) else 1.0
        shrink = A["peak_shrinkage"] if (peak_on and wknum in A["peak_weeks"]) else A["shrinkage"]
        c = calls[i] * uplift
        cases = (cases_bau[i] + change_cases[i]) * uplift
        in_house_cases = cases * (1 - A["outsourced_share"])
        hours = c * A["aht_call_min"] / 60 + in_house_cases * A["aht_case_min"] / 60
        ph = productive_hours(shrink)
        req = hours / ph
        gap = max(0.0, req - available[i])
        gap_hours = gap * ph
        ot_hours = available[i] * A["overtime_hours_per_fte"]
        residual = max(0.0, gap_hours - ot_hours)
        temp_fte = math.ceil(residual / ph) if residual > 0 else 0
        provider_cases = cases * A["outsourced_share"]
        rows.append({
            "scenario": name, "week_no": wknum, "week_start": wk,
            "calls": round(c), "total_cases": round(cases),
            "workload_hours": round(hours, 1), "productive_hours_per_fte": round(ph, 2),
            "required_fte": round(req, 1), "available_fte": round(available[i], 1),
            "gap_fte": round(gap, 1), "overtime_hours_available": round(ot_hours, 1),
            "temp_or_recruit_fte_needed": temp_fte,
            "provider_cases_forecast": round(provider_cases),
            "provider_cap": A["provider_weekly_cap_cases"],
            "provider_over_cap": bool(provider_cases > A["provider_weekly_cap_cases"]),
        })
    return pd.DataFrame(rows)


def main():
    df = pd.read_csv("data/service_ops_demand.csv", parse_dates=["week_start"])
    h = A["horizon_weeks"]

    # 1. Backtest
    acc_frames, backtest_rows, best_models, rmse_best = [], [], {}, {}
    for col in ["calls", "cases_bau"]:
        res, best, fc, test = backtest(df, col)
        acc_frames.append(res)
        best_models[col] = best
        rmse_best[col] = float(res.loc[res.model == best, "RMSE"].iloc[0])
        weeks = df["week_start"].iloc[-A["holdout_weeks"]:].dt.date.values
        for w, a, f in zip(weeks, test.values, fc):
            var = (a - f) / a * 100
            backtest_rows.append({"week_start": w, "series": col, "model": best,
                                  "actual": int(a), "forecast": round(f),
                                  "variance_pct": round(var, 1),
                                  "flag": abs(var) > A["variance_flag_pct"]})
    accuracy = pd.concat(acc_frames, ignore_index=True)
    bt = pd.DataFrame(backtest_rows)

    # 2. Forecast the next 13 weeks with the best model per series
    last = df["week_start"].iloc[-1]
    future_weeks = pd.date_range(last + pd.Timedelta(weeks=1), periods=h, freq="W-MON")
    fc_out = pd.DataFrame({"week_no": range(1, h + 1), "week_start": future_weeks.date})
    for col in ["calls", "cases_bau"]:
        f = MODELS[best_models[col]](df[col], h)
        z = A["interval_z"] * rmse_best[col]
        fc_out[f"{col}_forecast"] = np.round(f).astype(int)
        fc_out[f"{col}_low"] = np.round(f - z).astype(int)
        fc_out[f"{col}_high"] = np.round(f + z).astype(int)

    # 3. Available FTE: current level plus known staffing movements
    base_fte = float(df["fte_available"].iloc[-4:].mean())
    available, running = [], base_fte
    for w in range(1, h + 1):
        running += A["planned_fte_changes"].get(w, 0)
        available.append(running)

    calls = fc_out["calls_forecast"].values
    cases = fc_out["cases_bau_forecast"].values
    none = np.zeros(h)
    change = np.zeros(h)
    for wk, r in zip(A["change_weeks"], A["change_ramp"]):
        change[wk - 1] = A["change_cases_per_week"] * r

    wk_list = fc_out["week_start"].values
    plan = pd.concat([
        capacity_for_scenario("1 Base (BAU only)", calls, cases, none, wk_list, available, False),
        capacity_for_scenario("2 Base + change project", calls, cases, change, wk_list, available, False),
        capacity_for_scenario("3 Change + peak + absence", calls, cases, change, wk_list, available, True),
    ], ignore_index=True)

    summary = plan.groupby("scenario").agg(
        peak_required_fte=("required_fte", "max"),
        weeks_short=("gap_fte", lambda s: int((s > 0).sum())),
        peak_gap_fte=("gap_fte", "max"),
        max_temp_fte_after_overtime=("temp_or_recruit_fte_needed", "max"),
        weeks_provider_over_cap=("provider_over_cap", "sum"),
    ).reset_index()

    # 4. Save outputs
    accuracy.to_csv("outputs/accuracy_backtest.csv", index=False)
    bt.to_csv("outputs/backtest_weekly.csv", index=False)
    fc_out.to_csv("outputs/forecast_13wk.csv", index=False)
    plan.to_csv("outputs/capacity_plan.csv", index=False)
    summary.to_csv("outputs/scenario_summary.csv", index=False)
    pd.DataFrame([{"assumption": k, "value": json.dumps(v) if isinstance(v, (dict, list)) else v}
                  for k, v in A.items()]).to_csv("outputs/assumptions.csv", index=False)
    key = {"best_models": best_models, "available_fte_start": round(base_fte, 1),
           "productive_hours_per_fte": round(productive_hours(), 2),
           "accuracy": accuracy.to_dict("records"), "scenarios": summary.to_dict("records")}
    with open("outputs/key_results.json", "w") as f:
        json.dump(key, f, indent=2, default=str)

    print("BEST MODELS:", best_models)
    print("\nACCURACY (13-week holdout)\n", accuracy.to_string(index=False))
    print(f"\nProductive hours per FTE per week: {productive_hours():.2f}; starting FTE {base_fte:.1f}")
    print("\nFORECAST\n", fc_out.to_string(index=False))
    print("\nSCENARIO SUMMARY\n", summary.to_string(index=False))
    print("\nBACKTEST FLAGS:", int(bt.flag.sum()), "of", len(bt), "weeks beyond +/-", A["variance_flag_pct"], "%")


if __name__ == "__main__":
    main()
