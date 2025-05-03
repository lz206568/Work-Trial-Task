# Optimal Order Allocation in Limit Order Markets

This project implements a Smart Order Router using the Cont & Kukanov static cost model in a limit order market circumstance. The task simulates buying 5,000 shares over a short window and allocates orders across multiple trading venues to minimize total cost.


## 1. Approach Overview

We implement and compare the following strategies:

- **Best Ask Strategy**: Always buys from the current best ask price until the order size meets. Assumes fullfill at that price.
- **TWAP (Time-Weighted Average Price)**: Splits the total order equally across 60-second time buckets and buys proportionally.
- **VWAP (Volume-Weighted Average Price)**: Allocates order volume based on the available size in each time bucket.
- **Optimal Allocation (Model-Based)**: Distributes orders across simulated exchanges based on implementation costs, fees, rebates, and queue risks. The model uses exhaustive search to minimize total cost.

Each strategy tracks cumulative cost as it progresses, and its performance is compared visually and numerically.


## 2. Parameter Ranges (for Optimization Model)

In the model-based strategy, the optimizer explores parameter combinations:

- `λ_over`: Penalty for buying more than the order size  
  - Range: `np.linspace(0.5, 1.5, 3)` → `[0.5, 1.0, 1.5]`
- `λ_under`: Penalty for buying less than the order size  
  - Range: `np.linspace(0.5, 1.5, 3)` → `[0.5, 1.0, 1.5]`
- `θ_queue`: Penalty for total size due to queue risk  
  - Range: `np.linspace(0.05, 0.15, 3)` → `[0.05, 0.10, 0.15]`
  
Each parameter combination is evaluated over a fixed time under venue conditions, and the one minimizing cost is selected.


## 3. Improving Fill Realism (Idea for Future Work)

To improve the realism of fills:

### Slippage Modeling
In practice, submitting a large market order can move the price against the trader, which is a phenomenon known as slippage. To simulate this, we could introduce a slippage adjustment where the effective purchase price increases with the proportion of liquidity consumed. This would capture the cost of market impact, especially in less liquid trading.

### Queue Position Effects
Our current model assumes that all submitted orders are filled immediately if volume is available. However, in real markets, execution depends heavily on order position in the queue. A more realistic simulation should probabilistically fill based on the queue, where orders further back in the line have lower chances of execution within a given time.

These improvements would make the simulation reflect more about the real market and could lead to optimization results.


## 4. Interpreting the Plot: Why the Curves Appear Overlapping

In the output file results.pdf, the cumulative cost curves for the Best Ask, TWAP, and VWAP strategies appear to overlap closely. This might suggest that the strategies perform almost identically, but two underlying factors drive this visual similarity:

### Simulated Venue Characteristics
All three strategies interact with the same simulated trading venues, which have relatively similar fee structures, price levels, and available liquidity. Because the differences between the venues are small, and each strategy ultimately buys from the same pool of liquidity, the results are close together. This is true when the simulated venues have minimal variation in ask prices, ask_size.

### Data and Plot Resolution
The plot contains the cumulative cost of purchasing 5,000 shares, a relatively small range in financial trading. In this limited window, cost accumulation seems about linear, and the slight differences between the strategies become visually compressed. If we were to use scatter plots instead of line graphs, the fine-grained differences in implementation path, such as slight cost deviations at certain share thresholds, would become more visible. Similarly, plotting over a larger order size would likely intensify the differences and provide a clearer picture of how strategy performance separates over time.

In summary, while the strategies are indeed distinct in logic and behavior, the venue setup and visual scaling make them appear deceptively similar in the output plot.

By Lily Zhang
