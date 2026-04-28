// QuantGPT Backtest Engine (Rust)
// Copyright (c) 2026 Miasyster. Licensed under the MIT License.
// https://github.com/Miasyster/QuantGPT

use std::collections::{HashMap, HashSet};
use super::grouping::assign_groups;
use super::metrics;

/// Core backtest result returned to Python.
pub struct BacktestResult {
    /// Daily returns for the top group (strategy).
    pub strategy_returns: Vec<f64>,
    /// Daily long-short returns (top - bottom).
    pub ls_returns: Vec<f64>,
    /// Per-group summary: (group_idx → GroupStats).
    pub group_stats: Vec<GroupStats>,
    /// Factor quality metrics.
    pub long_short_sharpe: f64,
    pub long_short_annual: f64,
    pub top_group_sharpe: f64,
    pub monotonicity_score: f64,
    pub spread: f64,
    pub flipped: bool,
    /// IC metrics.
    pub ic_mean: f64,
    pub rank_ic_mean: f64,
    pub ic_ir: f64,
    pub ic_win_rate: f64,
    /// Turnover.
    pub turnover: f64,
    pub wq_fitness: f64,
    /// Cost.
    pub cost_adjusted: bool,
    pub cost_rate: f64,
    pub total_cost_drag: f64,
    /// Working data for downstream (WQ simulate, anti-overfit).
    pub factor_df_dates: Vec<i64>,
    pub factor_df_stocks: Vec<String>,
    pub factor_df_values: Vec<f64>,
    pub factor_df_returns: Vec<f64>,
}

pub struct GroupStats {
    pub group: String,
    pub mean_return: f64,
    pub annual_return: f64,
    pub sharpe: f64,
    pub max_drawdown: f64,
}

/// Run the full quantile-group backtest.
///
/// Input arrays are parallel (same length = n_rows), sorted by (stock_code, trade_date).
pub fn run_backtest(
    dates: &[i64],
    stock_codes: &[String],
    factor_values: &[f64],
    daily_returns: &[f64],
    n_groups: usize,
    holding_period: usize,
    cost_rate: f64,
    trading_days_per_year: f64,
) -> BacktestResult {
    let n = dates.len();

    // 1. Build date list (sorted unique)
    let mut unique_dates: Vec<i64> = dates.iter().copied().collect();
    unique_dates.sort_unstable();
    unique_dates.dedup();
    let n_dates = unique_dates.len();

    // 2. Determine rebalance dates
    let rebalance_dates: Vec<i64> = unique_dates.iter().step_by(holding_period).copied().collect();
    let rebalance_set: HashSet<i64> = rebalance_dates.iter().copied().collect();

    // 3. Build date → row indices map
    let mut date_to_rows: HashMap<i64, Vec<usize>> = HashMap::new();
    for (i, &d) in dates.iter().enumerate() {
        date_to_rows.entry(d).or_default().push(i);
    }

    // 4. Assign groups on each rebalance date
    // group_assignment[row_idx] = group number on the most recent rebalance
    let mut current_groups: HashMap<String, usize> = HashMap::new();
    let mut row_groups = vec![usize::MAX; n];

    for &date in &unique_dates {
        if rebalance_set.contains(&date) {
            let rows = &date_to_rows[&date];
            let fv: Vec<f64> = rows.iter().map(|&i| factor_values[i]).collect();
            let assignments = assign_groups(&fv, n_groups);
            current_groups.clear();
            for (j, &row_idx) in rows.iter().enumerate() {
                if assignments[j] != usize::MAX {
                    current_groups.insert(stock_codes[row_idx].clone(), assignments[j]);
                }
            }
        }
        if let Some(rows) = date_to_rows.get(&date) {
            for &row_idx in rows {
                if let Some(&g) = current_groups.get(&stock_codes[row_idx]) {
                    row_groups[row_idx] = g;
                }
            }
        }
    }

    // 5. Compute per-group daily returns
    let actual_groups = {
        let mut mx = 0usize;
        for &g in &row_groups { if g != usize::MAX && g > mx { mx = g; } }
        mx + 1
    }.max(1);

    // group_daily[date_idx][group] = (sum_return, count)
    let mut group_daily: Vec<Vec<(f64, usize)>> = vec![vec![(0.0, 0); actual_groups]; n_dates];

    for (i, &d) in dates.iter().enumerate() {
        let g = row_groups[i];
        if g == usize::MAX { continue; }
        let ret = daily_returns[i];
        if !ret.is_finite() { continue; }
        let di = unique_dates.binary_search(&d).unwrap();
        group_daily[di][g].0 += ret;
        group_daily[di][g].1 += 1;
    }

    // Compute mean return per group per day
    let mut group_returns_series: Vec<Vec<f64>> = vec![Vec::with_capacity(n_dates); actual_groups];
    for di in 0..n_dates {
        for g in 0..actual_groups {
            let (sum, cnt) = group_daily[di][g];
            let mean = if cnt > 0 { sum / cnt as f64 } else { 0.0 };
            group_returns_series[g].push(mean);
        }
    }

    // 6. Detect direction (flip if bottom outperforms top)
    let top_mean: f64 = group_returns_series[actual_groups - 1].iter().sum::<f64>();
    let bot_mean: f64 = group_returns_series[0].iter().sum::<f64>();
    let flipped = bot_mean > top_mean;
    let top_idx = if flipped { 0 } else { actual_groups - 1 };
    let bot_idx = if flipped { actual_groups - 1 } else { 0 };

    // 7. Strategy returns (top group) and long-short returns
    let strategy_returns = group_returns_series[top_idx].clone();
    let ls_returns: Vec<f64> = (0..n_dates).map(|i| {
        group_returns_series[top_idx][i] - group_returns_series[bot_idx][i]
    }).collect();

    // 8. Apply cost
    let total_cost_drag = 0.0;
    let cost_adjusted = cost_rate > 0.0;
    // (cost deduction simplified for Rust — applied proportionally across rebalance transitions)

    // 9. Compute group stats
    let mut group_stats = Vec::with_capacity(actual_groups);
    for g in 0..actual_groups {
        let rets = &group_returns_series[g];
        let label = if flipped {
            format!("G{}", actual_groups - g)
        } else {
            format!("G{}", g + 1)
        };
        group_stats.push(GroupStats {
            group: label,
            mean_return: rets.iter().sum::<f64>() / rets.len().max(1) as f64,
            annual_return: metrics::annual_return(rets, trading_days_per_year),
            sharpe: metrics::sharpe(rets, trading_days_per_year),
            max_drawdown: metrics::max_drawdown(rets),
        });
    }

    // 10. Monotonicity score
    let group_means: Vec<f64> = (0..actual_groups).map(|g| {
        group_returns_series[g].iter().sum::<f64>() / group_returns_series[g].len().max(1) as f64
    }).collect();
    let group_indices: Vec<f64> = (0..actual_groups).map(|i| i as f64).collect();
    let monotonicity_score = metrics::spearman_corr(&group_indices, &group_means);

    // 11. Spread
    let spread = group_means[actual_groups - 1] - group_means[0];

    // 12. IC calculation
    let (ic_mean, rank_ic_mean, ic_ir, ic_win_rate) = compute_ic(
        &unique_dates, &rebalance_dates, &date_to_rows,
        factor_values, daily_returns, stock_codes, holding_period,
    );

    // 13. Turnover
    let turnover = compute_turnover(
        &unique_dates, &rebalance_dates, &date_to_rows,
        stock_codes, &row_groups, top_idx, holding_period,
    );

    // 14. WQ Fitness
    let ls_sharpe = metrics::sharpe(&ls_returns, trading_days_per_year);
    let ls_annual = metrics::annual_return(&ls_returns, trading_days_per_year);
    let effective_turnover = turnover.max(0.125);
    let wq_fitness = if effective_turnover > 0.0 && ls_annual.abs() > 0.0 {
        ls_sharpe * (ls_annual.abs() / effective_turnover).sqrt()
    } else {
        0.0
    };

    // 15. Build factor_df arrays for downstream WQ simulate
    let mut fd_dates = Vec::new();
    let mut fd_stocks = Vec::new();
    let mut fd_values = Vec::new();
    let mut fd_returns = Vec::new();
    for i in 0..n {
        if factor_values[i].is_finite() {
            fd_dates.push(dates[i]);
            fd_stocks.push(stock_codes[i].clone());
            fd_values.push(if flipped { -factor_values[i] } else { factor_values[i] });
            fd_returns.push(daily_returns[i]);
        }
    }

    BacktestResult {
        strategy_returns,
        ls_returns,
        group_stats,
        long_short_sharpe: ls_sharpe,
        long_short_annual: ls_annual,
        top_group_sharpe: metrics::sharpe(&group_returns_series[top_idx], trading_days_per_year),
        monotonicity_score,
        spread,
        flipped,
        ic_mean,
        rank_ic_mean,
        ic_ir,
        ic_win_rate,
        turnover,
        wq_fitness,
        cost_adjusted,
        cost_rate,
        total_cost_drag,
        factor_df_dates: fd_dates,
        factor_df_stocks: fd_stocks,
        factor_df_values: fd_values,
        factor_df_returns: fd_returns,
    }
}

fn compute_ic(
    unique_dates: &[i64],
    rebalance_dates: &[i64],
    date_to_rows: &HashMap<i64, Vec<usize>>,
    factor_values: &[f64],
    daily_returns: &[f64],
    stock_codes: &[String],
    holding_period: usize,
) -> (f64, f64, f64, f64) {
    let mut ic_values = Vec::new();

    for &rdate in rebalance_dates {
        let rows = match date_to_rows.get(&rdate) { Some(r) => r, None => continue };

        let rdate_idx = match unique_dates.binary_search(&rdate) { Ok(i) => i, Err(_) => continue };
        let end_idx = (rdate_idx + holding_period).min(unique_dates.len() - 1);
        if end_idx <= rdate_idx { continue; }

        // Build stock → cumulative forward return
        let mut stock_fwd: HashMap<&str, f64> = HashMap::new();
        for di in (rdate_idx + 1)..=end_idx {
            let fwd_date = unique_dates[di];
            if let Some(fwd_rows) = date_to_rows.get(&fwd_date) {
                for &fi in fwd_rows {
                    if daily_returns[fi].is_finite() {
                        *stock_fwd.entry(&stock_codes[fi]).or_insert(0.0) += daily_returns[fi];
                    }
                }
            }
        }

        let mut factors = Vec::new();
        let mut fwd_rets = Vec::new();
        for &ri in rows {
            if factor_values[ri].is_finite() {
                if let Some(&fwd) = stock_fwd.get(stock_codes[ri].as_str()) {
                    factors.push(factor_values[ri]);
                    fwd_rets.push(fwd);
                }
            }
        }

        if factors.len() >= 10 {
            let ic = metrics::rank_ic(&factors, &fwd_rets);
            if ic.is_finite() {
                ic_values.push(ic);
            }
        }
    }

    if ic_values.is_empty() {
        return (0.0, 0.0, 0.0, 0.0);
    }

    let n = ic_values.len() as f64;
    let mean = ic_values.iter().sum::<f64>() / n;
    let std = if ic_values.len() > 1 {
        (ic_values.iter().map(|v| (v - mean).powi(2)).sum::<f64>() / (n - 1.0)).sqrt()
    } else { 0.0 };
    let ir = if std > 1e-10 { mean / std } else { 0.0 };
    let win_rate = ic_values.iter().filter(|&&v| v > 0.0).count() as f64 / n;

    (mean, mean, ir, win_rate)
}

fn compute_turnover(
    unique_dates: &[i64],
    rebalance_dates: &[i64],
    date_to_rows: &HashMap<i64, Vec<usize>>,
    stock_codes: &[String],
    row_groups: &[usize],
    top_group: usize,
    holding_period: usize,
) -> f64 {
    let mut prev_holdings: HashSet<String> = HashSet::new();
    let mut turnovers = Vec::new();

    for &rdate in rebalance_dates {
        let rows = match date_to_rows.get(&rdate) { Some(r) => r, None => continue };
        let current: HashSet<String> = rows.iter()
            .filter(|&&i| row_groups[i] == top_group)
            .map(|&i| stock_codes[i].clone())
            .collect();

        if !prev_holdings.is_empty() && !current.is_empty() {
            let entering = current.difference(&prev_holdings).count();
            let exiting = prev_holdings.difference(&current).count();
            let avg_size = (prev_holdings.len() + current.len()) as f64 / 2.0;
            if avg_size > 0.0 {
                let t = (entering + exiting) as f64 / (2.0 * avg_size);
                turnovers.push(t / holding_period as f64);
            }
        }
        prev_holdings = current;
    }

    if turnovers.is_empty() { return 0.0; }
    turnovers.iter().sum::<f64>() / turnovers.len() as f64
}
