# Project Notes

The decisions and findings behind *Too Good to Be True*, written as the work happens so every number in the slides traces back to a dated, committed note. Read them in this order.

| Note | What it Answers | Status |
| --- | --- | --- |
| [`data.md`](data.md) | What data is used, what was checked or dropped, and how to reproduce it | Done (11/20)|
| [`eda.md`](eda.md) | What the data looks like before any tuning, and what that predicts | Done (11/21)|
| [`case_study.md`](case_study.md) | Does a famous published trading rule still work after publication? Rules and pass criteria fixed before the run | Pre-registered (11/21); verdict after results-v1 |
| [`debugging.md`](debugging.md) | What broke, why, and how it was fixed and checked | Ongoing |
| `costs.md` | Where each cost assumption (fees, spreads, market impact) comes from |  |
| `results.md` | The headline numbers: the strategy funnel, PBO, shrinkage, break-even fees, validation | (`results-v1`, `results-v2`) |

**The Question:** How much of a backtest's performance is real, and can we tell in advance which strategies will hold up?

**Ground Rules:**
- Strategies are chosen on in-sample data only. The out-of-sample starts (crypto 2023-01-01, ETFs 2018-01-01) never move.
- Anything written before seeing results stays as written; later findings are added, not edited in.