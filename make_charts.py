"""Charts for the service operations planning model. Run after forecast_and_capacity.py."""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
BLUE, ORANGE, GREY = "#2a78d6", "#eb6834", "#898781"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": GRID,
                     "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED,
                     "axes.facecolor": SURFACE, "figure.facecolor": SURFACE,
                     "axes.spines.top": False, "axes.spines.right": False})
OUT = "outputs/charts"


def style(ax, months=3):
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=months))


def load():
    d = pd.read_csv("data/service_ops_demand.csv", parse_dates=["week_start"])
    bt = pd.read_csv("outputs/backtest_weekly.csv", parse_dates=["week_start"])
    fc = pd.read_csv("outputs/forecast_13wk.csv", parse_dates=["week_start"])
    plan = pd.read_csv("outputs/capacity_plan.csv", parse_dates=["week_start"])
    return d, bt, fc, plan


def forecast_chart(series, title, fname):
    d, bt, fc, _ = load()
    hist = d.tail(78)
    b = bt[bt.series == series]
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.plot(hist.week_start, hist[series], color=INK2, lw=1.4, label="Actual")
    ax.plot(b.week_start, b.forecast, color=ORANGE, lw=1.6, ls="--", label="Backtest forecast (13-week holdout)")
    ax.fill_between(fc.week_start, fc[f"{series}_low"], fc[f"{series}_high"], color=BLUE, alpha=0.15, lw=0, label="80% interval")
    ax.plot(fc.week_start, fc[f"{series}_forecast"], color=BLUE, lw=1.8, label="Forecast, next 13 weeks")
    ax.axvline(d.week_start.iloc[-1], color=GRID, lw=1)
    style(ax)
    ax.set_title(title, loc="left", color=INK, fontsize=11, fontweight="bold")
    ax.set_ylabel("Weekly volume")
    ax.legend(frameon=False, ncol=2, loc="upper left", fontsize=8, labelcolor=INK2)
    ax.set_ylim(top=hist[series].max() * 1.22)
    fig.text(0.01, 0.01, "Simulated data. Interval = forecast +/- 1.28 x holdout RMSE.", fontsize=7, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(f"{OUT}/{fname}", dpi=160)
    plt.close(fig)


def capacity_chart():
    _, _, _, plan = load()
    names = plan.scenario.unique()
    fig, axes = plt.subplots(3, 1, figsize=(9, 7.4), sharex=True, sharey=True)
    for a in axes: a.tick_params(labelbottom=True)
    for ax, n in zip(axes, names):
        p = plan[plan.scenario == n]
        ax.fill_between(p.week_start, p.available_fte, p.required_fte, where=p.required_fte > p.available_fte,
                        color=ORANGE, alpha=0.35, lw=0, label="Shortfall")
        ax.plot(p.week_start, p.available_fte, color=INK2, lw=1.6, drawstyle="steps-post", label="Available FTE")
        ax.plot(p.week_start, p.required_fte, color=BLUE, lw=1.8, label="Required FTE")
        style(ax, 1)
        ax.set_title(n, loc="left", color=INK, fontsize=10, fontweight="bold")
        ax.set_ylabel("FTE")
    axes[0].legend(frameon=False, ncol=3, loc="upper left", fontsize=8, labelcolor=INK2)
    axes[0].set_ylim(40, 88)
    fig.text(0.01, 0.005, "Simulated data. Required FTE = workload hours / productive hours per FTE.", fontsize=7, color=MUTED)
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(f"{OUT}/capacity_scenarios.png", dpi=160)
    plt.close(fig)


def provider_chart():
    _, _, _, plan = load()
    cols = {plan.scenario.unique()[0]: GREY, plan.scenario.unique()[1]: BLUE, plan.scenario.unique()[2]: ORANGE}
    fig, ax = plt.subplots(figsize=(9, 3.6))
    for n, c in cols.items():
        p = plan[plan.scenario == n]
        ax.plot(p.week_start, p.provider_cases_forecast, color=c, lw=1.8, label=n)
    ax.axhline(plan.provider_cap.iloc[0], color=INK, lw=1, ls="--")
    ax.text(plan.week_start.iloc[0], plan.provider_cap.iloc[0] + 8, "Contracted weekly cap", fontsize=8, color=INK2)
    style(ax, 1)
    ax.set_title("Outsourced provider: forecast cases vs contracted volume", loc="left", color=INK, fontsize=11, fontweight="bold")
    ax.set_ylabel("Cases per week")
    ax.legend(frameon=False, ncol=3, loc="upper left", fontsize=8, labelcolor=INK2)
    ax.set_ylim(500, 1000)
    fig.text(0.01, 0.01, "Simulated data. Cap is an illustrative assumption.", fontsize=7, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(f"{OUT}/provider_vs_cap.png", dpi=160)
    plt.close(fig)


def main():
    os.makedirs(OUT, exist_ok=True)
    forecast_chart("calls", "Telephony: actual, backtest and 13-week forecast", "forecast_calls.png")
    forecast_chart("cases_bau", "Back-office cases (BAU): actual, backtest and 13-week forecast", "forecast_cases.png")
    capacity_chart()
    provider_chart()
    print("Charts written to", OUT)


if __name__ == "__main__":
    main()
