/// Annualized Sharpe ratio.
pub fn sharpe(daily_returns: &[f64], periods_per_year: f64) -> f64 {
    let vals: Vec<f64> = daily_returns.iter().copied().filter(|v| v.is_finite()).collect();
    if vals.len() < 2 { return 0.0; }
    let n = vals.len() as f64;
    let mean = vals.iter().sum::<f64>() / n;
    let std = (vals.iter().map(|v| (v - mean).powi(2)).sum::<f64>() / (n - 1.0)).sqrt();
    if std < 1e-15 { return 0.0; }
    mean / std * periods_per_year.sqrt()
}

/// Annualized Sortino ratio (downside deviation).
pub fn sortino(daily_returns: &[f64], periods_per_year: f64) -> f64 {
    let vals: Vec<f64> = daily_returns.iter().copied().filter(|v| v.is_finite()).collect();
    if vals.len() < 2 { return 0.0; }
    let n = vals.len() as f64;
    let mean = vals.iter().sum::<f64>() / n;
    let downside_var = vals.iter().map(|v| v.min(0.0).powi(2)).sum::<f64>() / (n - 1.0);
    let downside_std = downside_var.sqrt();
    if downside_std < 1e-15 { return 0.0; }
    mean / downside_std * periods_per_year.sqrt()
}

/// Maximum drawdown (as positive fraction).
pub fn max_drawdown(daily_returns: &[f64]) -> f64 {
    let mut peak = 1.0_f64;
    let mut nav = 1.0_f64;
    let mut max_dd = 0.0_f64;
    for &r in daily_returns {
        if !r.is_finite() { continue; }
        nav *= 1.0 + r;
        if nav > peak { peak = nav; }
        let dd = (peak - nav) / peak;
        if dd > max_dd { max_dd = dd; }
    }
    max_dd
}

/// Annualized return.
pub fn annual_return(daily_returns: &[f64], periods_per_year: f64) -> f64 {
    let vals: Vec<f64> = daily_returns.iter().copied().filter(|v| v.is_finite()).collect();
    if vals.is_empty() { return 0.0; }
    let mean = vals.iter().sum::<f64>() / vals.len() as f64;
    (1.0 + mean).powf(periods_per_year) - 1.0
}

/// Annualized volatility.
pub fn volatility(daily_returns: &[f64], periods_per_year: f64) -> f64 {
    let vals: Vec<f64> = daily_returns.iter().copied().filter(|v| v.is_finite()).collect();
    if vals.len() < 2 { return 0.0; }
    let n = vals.len() as f64;
    let mean = vals.iter().sum::<f64>() / n;
    let var = vals.iter().map(|v| (v - mean).powi(2)).sum::<f64>() / (n - 1.0);
    var.sqrt() * periods_per_year.sqrt()
}

/// Win rate (fraction of positive returns).
pub fn win_rate(daily_returns: &[f64]) -> f64 {
    let vals: Vec<f64> = daily_returns.iter().copied().filter(|v| v.is_finite()).collect();
    if vals.is_empty() { return 0.0; }
    let wins = vals.iter().filter(|&&v| v > 0.0).count();
    wins as f64 / vals.len() as f64
}

/// Profit factor (sum of gains / sum of losses).
pub fn profit_factor(daily_returns: &[f64]) -> f64 {
    let mut gains = 0.0_f64;
    let mut losses = 0.0_f64;
    for &r in daily_returns {
        if !r.is_finite() { continue; }
        if r > 0.0 { gains += r; } else { losses += -r; }
    }
    if losses < 1e-15 { return if gains > 0.0 { 100.0 } else { 0.0 }; }
    gains / losses
}

/// Spearman rank correlation (for monotonicity score).
pub fn spearman_corr(x: &[f64], y: &[f64]) -> f64 {
    assert_eq!(x.len(), y.len());
    let n = x.len();
    if n < 3 { return 0.0; }
    let rx = ranks(x);
    let ry = ranks(y);
    pearson(&rx, &ry)
}

/// Rank IC: Spearman correlation between factor values and forward returns.
pub fn rank_ic(factor: &[f64], fwd_returns: &[f64]) -> f64 {
    let pairs: Vec<(f64, f64)> = factor.iter().zip(fwd_returns.iter())
        .filter(|(&f, &r)| f.is_finite() && r.is_finite())
        .map(|(&f, &r)| (f, r))
        .collect();
    if pairs.len() < 10 { return f64::NAN; }
    let f: Vec<f64> = pairs.iter().map(|(f, _)| *f).collect();
    let r: Vec<f64> = pairs.iter().map(|(_, r)| *r).collect();
    spearman_corr(&f, &r)
}

/// Pearson correlation.
pub fn pearson(x: &[f64], y: &[f64]) -> f64 {
    let n = x.len() as f64;
    if n < 2.0 { return 0.0; }
    let mx = x.iter().sum::<f64>() / n;
    let my = y.iter().sum::<f64>() / n;
    let mut cov = 0.0;
    let mut vx = 0.0;
    let mut vy = 0.0;
    for i in 0..x.len() {
        let dx = x[i] - mx;
        let dy = y[i] - my;
        cov += dx * dy;
        vx += dx * dx;
        vy += dy * dy;
    }
    let denom = (vx * vy).sqrt();
    if denom < 1e-15 { 0.0 } else { cov / denom }
}

fn ranks(vals: &[f64]) -> Vec<f64> {
    let n = vals.len();
    let mut indexed: Vec<(usize, f64)> = vals.iter().enumerate().map(|(i, &v)| (i, v)).collect();
    indexed.sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(std::cmp::Ordering::Equal));
    let mut result = vec![0.0; n];
    for (rank, &(idx, _)) in indexed.iter().enumerate() {
        result[idx] = rank as f64;
    }
    result
}
