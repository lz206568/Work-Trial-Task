#!/usr/bin/env python
# coding: utf-8

# In[1]:


import pandas as pd
import numpy as np
import json
import matplotlib.pyplot as plt


# In[2]:


# Read and process data
def process_data(file_path):
    data = pd.read_csv(file_path)
    # For each ts_event, keep only the first message from each publisher_id
    data = data.groupby(['ts_event']).first().reset_index()

    return data


# In[3]:


# Best ask price strategy
def best_ask_strategy(data, order_size=5000):
    total_cash_spent = 0
    total_shares_bought = 0
    cumulative_costs = []
    for _, row in data.iterrows():
        ask_price = row['ask_px_00']  # current best ask price
        ask_size = row['ask_sz_00']  # current best ask size
        if total_shares_bought >= order_size:
            break
        buy_amount = min(order_size - total_shares_bought, ask_size)
        total_cash_spent += buy_amount * ask_price
        total_shares_bought += buy_amount
        cumulative_costs.append([total_shares_bought, total_cash_spent])
    average_fill_price = total_cash_spent / total_shares_bought
    return total_cash_spent, average_fill_price, cumulative_costs


# In[4]:


# 60-second Time-Weighted Average Price (TWAP) strategy
def twap_strategy(data, order_size=5000):
    data['ts_event'] = pd.to_datetime(data['ts_event'])
    start_time = data['ts_event'].min()
    end_time = data['ts_event'].max()
    time_buckets = pd.date_range(start=start_time, end=end_time, freq='60S')
    shares_per_bucket = order_size / len(time_buckets)  # shares to buy per minute
    total_cash_spent = 0
    total_shares_bought = 0
    cumulative_costs = []
    for i in range(len(time_buckets) - 1):
        bucket_start = time_buckets[i]
        bucket_end = time_buckets[i + 1]
        bucket_data = data[(data['ts_event'] >= bucket_start) & (data['ts_event'] < bucket_end)]
        bucket_shares_bought = 0
        for _, row in bucket_data.iterrows():
            ask_price = row['ask_px_00']
            ask_size = row['ask_sz_00']
            if total_shares_bought >= order_size or bucket_shares_bought >= shares_per_bucket:
                break
            buy_amount = min(shares_per_bucket - bucket_shares_bought, order_size - total_shares_bought, ask_size)
            total_cash_spent += buy_amount * ask_price
            total_shares_bought += buy_amount
            bucket_shares_bought += buy_amount
            cumulative_costs.append([total_shares_bought, total_cash_spent])

    average_fill_price = total_cash_spent / total_shares_bought
    return total_cash_spent, average_fill_price, cumulative_costs


# In[5]:


# Volume-Weighted Average Price (VWAP) strategy
def vwap_strategy(data, order_size=5000):
    total_volume = data['ask_sz_00'].sum()  # total available volume at best ask
    total_cash_spent = 0
    total_shares_bought = 0
    cumulative_costs = []
    for _, row in data.iterrows():
        ask_price = row['ask_px_00']
        ask_size = row['ask_sz_00']
        share_ratio = ask_size / total_volume
        target_shares = order_size * share_ratio
        if total_shares_bought >= order_size:
            break
        buy_amount = min(target_shares, ask_size)
        total_cash_spent += buy_amount * ask_price
        total_shares_bought += buy_amount
        cumulative_costs.append([total_shares_bought, total_cash_spent])

    average_fill_price = total_cash_spent / total_shares_bought
    return total_cash_spent, average_fill_price, cumulative_costs


# In[6]:


# Compute total cost of a given allocation
def compute_cost(split, venues, λ_over, λ_under, θ_queue):
    executed = 0         # number of shares actually executed
    cash_spent = 0       # total cash spent
    for i, v in enumerate(venues):
        exe = min(split[i], v['ask_size'])  # number of shares that can be executed: limited by ask size or order
        executed += exe
        cash_spent += exe * (v['ask'] + v['fee'])      # executed shares incur cost = price + fee
        cash_spent -= (split[i] - exe) * v['rebate']   # unexecuted shares receive rebate (if any)

    underfill = max(0, sum([v['ask_size'] for v in venues]) - executed)  # penalty for not filling all available volume
    overfill = max(0, executed - sum([v['ask_size'] for v in venues]))   # penalty for overfilling
    risk_pen = θ_queue * sum([s for s in split])                         # queueing risk penalty
    cost_pen = λ_under * underfill + λ_over * overfill                  # total penalty
    return cash_spent + risk_pen + cost_pen


# In[7]:


# Static allocation algorithm: find the optimal order distribution across multiple venues
# such that the total cost of buying order_size shares is minimized.
def allocate(order_size, venues, λ_over, λ_under, θ_queue):
    #   order_size  – target number of shares to buy (e.g. 5,000)
    #   venues      – list of venue objects, each with:
    #                 .ask  .ask_size  .fee  .rebate
    #   λ_over      – cost penalty for over-execution
    #   λ_under     – cost penalty for under-execution
    #   θ_queue     – queue risk penalty (linear in total quantity submitted)

    step = 100
    splits = [[]]

    # Generate all possible combinations of order splits across venues
    for v in venues:
        new_splits = []
        for s in splits:
            for i in range(0, min(order_size - sum(s), v['ask_size']) + 1, step):
                new_splits.append(s + [i])
        splits = new_splits

    best_cost = float('inf')
    best_split = []
    for split in splits:
        if sum(split) != order_size:
            continue
        cost = compute_cost(split, venues, λ_over, λ_under, θ_queue)
        if cost < best_cost:
            best_cost = cost
            best_split = split

    return best_split, best_cost


# In[8]:


# Search for the best parameter combination
def find_best_params(data, order_size=5000):
    # Define the search ranges for parameters
    lambda_over_range = np.linspace(0.5, 1.5, 3)
    lambda_under_range = np.linspace(0.5, 1.5, 3)
    theta_queue_range = np.linspace(0.05, 0.15, 3)

    best_cost = float('inf')
    best_params = None

    # Simulated venues with different price/size
    venues = [
        {'ask': 10.00, 'ask_size': 2000, 'fee': 0.01, 'rebate': 0.005},
        {'ask': 11.5, 'ask_size': 3000, 'fee': 0.01, 'rebate': 0.005},
        {'ask': 8.5, 'ask_size': 1500, 'fee': 0.01, 'rebate': 0.005},
    ]

    # Iterate over all possible parameter combinations
    for lambda_over in lambda_over_range:
        for lambda_under in lambda_under_range:
            for theta_queue in theta_queue_range:
                best_split, cost = allocate(order_size, venues, lambda_over, lambda_under, theta_queue)
                if cost < best_cost:
                    best_cost = cost
                    best_params = (lambda_over, lambda_under, theta_queue)

    return best_params, best_cost


# In[9]:


# Calculate cost savings (in basis points)
# Computes how much cheaper the optimized strategy is compared to the baseline
def calculate_savings_bps(baseline_avg_price, optimized_avg_price):
    return ((baseline_avg_price - optimized_avg_price) / baseline_avg_price) * 10000


# In[10]:


# Main function
def main():
    file_path = 'l1_day.csv'
    data = process_data(file_path)

    # Calculate baseline strategy metrics
    best_ask_total, best_ask_avg, best_ask_cumulative = best_ask_strategy(data)
    twap_total, twap_avg, twap_cumulative = twap_strategy(data)
    vwap_total, vwap_avg, vwap_cumulative = vwap_strategy(data)

    # Find the best parameter combination
    best_params, best_cost = find_best_params(data)

    # Calculate average fill price under optimal parameters
    best_avg_price = best_cost / 5000

    # Calculate savings vs. each baseline strategy (in basis points)
    best_ask_savings = calculate_savings_bps(best_ask_avg, best_avg_price)
    twap_savings = calculate_savings_bps(twap_avg, best_avg_price)
    vwap_savings = calculate_savings_bps(vwap_avg, best_avg_price)

    result = {
        "best_params": {
            "lambda_over": best_params[0],
            "lambda_under": best_params[1],
            "theta_queue": best_params[2]
        },
        "model": {
            "total_cash_spent": best_cost,
            "average_fill_price": best_avg_price
        },
        "best_ask": {
            "total_cash_spent": best_ask_total,
            "average_fill_price": best_ask_avg,
            "savings_bps": best_ask_savings
        },
        "twap": {
            "total_cash_spent": twap_total,
            "average_fill_price": twap_avg,
            "savings_bps": twap_savings
        },
        "vwap": {
            "total_cash_spent": vwap_total,
            "average_fill_price": vwap_avg,
            "savings_bps": vwap_savings
        }
    }

    # Convert result to JSON and print it
    json_result = json.dumps(result, indent=4)  # indent each level by 4 spaces
    print(json_result)

    # Generate cumulative cost plot
    x1 = [point[0] for point in best_ask_cumulative]
    y1 = [point[1] for point in best_ask_cumulative]
    x2 = [point[0] for point in twap_cumulative]
    y2 = [point[1] for point in twap_cumulative]
    x3 = [point[0] for point in vwap_cumulative[::2500]]
    y3 = [point[1] for point in vwap_cumulative[::2500]]
    print(len(best_ask_cumulative))
    print(len(twap_cumulative))
    print(len(vwap_cumulative))

    plt.figure(figsize=(10, 6))
    plt.plot(x1, y1, label='Best Ask')
    plt.plot(x2, y2, label='TWAP')
    plt.plot(x3, y3, label='VWAP')
    plt.xlabel('Shares Bought')
    plt.ylabel('Cumulative Cost')
    plt.title('Cumulative Cost Plot')
    plt.legend()

    # Save the plot as a PDF file
    plt.savefig('results.pdf')

    # Display the plot
    plt.show()


if __name__ == "__main__":
    main()


# In[ ]:









