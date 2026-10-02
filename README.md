# Service Operations Planning Model

Demand forecasting and workforce capacity planning for a customer operations team in financial services, built in Python with an Excel workbook that repeats the capacity logic using live formulas.

> **All data in this repository is simulated.** Volumes, handling times, staffing levels and the outsourced provider's contract cap are illustrative assumptions. They do not come from any real organisation, and the accuracy figures below show that the method works, not what accuracy to expect on real data.

## The question

A service operation handles inbound calls and back-office cases (transfers, account changes, document processing). For the next 13 weeks:

1. How much work should we expect?
2. How many people does that need?
3. Where will we be short, and what are the options for covering it?
4. Will the outsourced provider stay within its contracted volume?

## Results

Forecast accuracy on a 13-week holdout (weeks the model never saw):

| Series | Holt-Winters MAPE | Seasonal naive MAPE | Holt-Winters bias |
|---|---|---|---|
| Calls | 3.8% | 4.7% | -0.5% |
| Back-office cases | 5.2% | 5.5% | -2.5% |

No holdout week was more than 10% away from actual. Holt-Winters beats the "same week last year" benchmark on both series, by a clear margin for calls and a small one for cases.

![Telephony forecast](outputs/charts/forecast_calls.png)

![Back-office case forecast](outputs/charts/forecast_cases.png)

Capacity over the next 13 weeks (starting from 64.1 available FTE, with two assumed leavers in week 5 and three trained hires in week 9):

| Scenario | Peak required FTE | Weeks short | Peak gap (FTE) | Temp or recruited FTE after overtime | Weeks provider over cap |
|---|---|---|---|---|---|
| 1 Base (BAU only) | 65.4 | 1 | 3.3 | 0 | 0 |
| 2 Base + change project | 68.5 | 4 | 6.3 | 0 | 3 |
| 3 Change + peak + absence | 81.1 | 6 | 19.0 | 7 | 4 |

Scenario 3 is a deliberate stress test (10% more volume and 35% shrinkage in five peak weeks), not a prediction.

![Required vs available FTE by scenario](outputs/charts/capacity_scenarios.png)

![Outsourced provider volume against contract](outputs/charts/provider_vs_cap.png)

## How it works

**Data.** `generate_data.py` creates three years of weekly volumes with a 3% yearly trend, a tax-year-end peak in March and April, a quiet summer, a month-end uplift and a bank-holiday dip at year end. It also includes a past change-project campaign, the outsourced share of cases and in-house FTE.

**Forecast.** Business-as-usual demand is forecast separately from change-project demand, because change demand is a planned input, not a pattern to learn. Two models are compared on a 13-week holdout: a seasonal naive benchmark and Holt-Winters (damped trend, multiplicative seasonality). The better model per series is re-fitted on all history to forecast the next 13 weeks. The 80% interval is the forecast plus or minus 1.28 times the holdout RMSE.

**Capacity.**

- Workload hours = calls x handling time + in-house cases x handling time
- Productive hours per FTE = contracted hours x (1 - shrinkage) x occupancy
- Required FTE = workload hours / productive hours per FTE
- A shortfall is covered first by overtime (capped per FTE); the remainder is shown as temporary or recruited FTE needed

**Scenarios.** Base, base plus a planned change project, and change project plus peak volume plus higher absence.

**Outsourced provider.** Forecast provider volume is compared with the contracted weekly cap, and weeks over the cap are flagged.

## Assumptions (all illustrative)

| Assumption | Value |
|---|---|
| Handling time per call | 7 min |
| Handling time per back-office case | 22 min |
| Contracted hours per FTE | 37.5 per week |
| Shrinkage | 30% (35% in scenario 3 peak weeks) |
| Occupancy | 85% |
| Share of cases routed to the outsourced provider | 25% |
| Provider contracted weekly volume | 800 cases |
| Overtime cap | 4 hours per FTE per week |
| Change project | up to 350 extra cases per week over six weeks |

All assumptions are in the `ASSUMPTIONS` block at the top of `forecast_and_capacity.py` and on the Assumptions tab of the workbook.

## Repository contents

| Path | What it is |
|---|---|
| `generate_data.py` | Creates the simulated weekly dataset |
| `data/service_ops_demand.csv` | The simulated data |
| `forecast_and_capacity.py` | Forecast, backtest, capacity and scenario model |
| `make_charts.py` | Creates the charts |
| `notebook.ipynb` | Step-by-step walkthrough with plain-English explanations |
| `Service_Ops_Planning_Model.xlsx` | Workbook with live capacity formulas and a scenario selector |
| `build_workbook.py`, `build_notebook.py` | Scripts that build the workbook and notebook |
| `outputs/` | Forecast, capacity plan, accuracy tables and charts |

## Run it

```
pip install -r requirements.txt
python generate_data.py
python forecast_and_capacity.py
python make_charts.py
```

The workbook formulas calculate when it is opened in Excel. The forecast values on its Forecast tab are pasted from the Python output, and everything downstream of them is a live formula.

## Limitations

- Simulated data with regular seasonality is easier to forecast than real demand.
- Handling time, shrinkage and occupancy are single averages. In practice they vary by team and season.
- Weekly granularity hides day-of-week and intraday patterns. A telephony staffing plan would normally use an Erlang C calculation on interval data.
- With real data, forecast accuracy would be tracked every week, with a reforecast whenever variance moves past an agreed threshold.
