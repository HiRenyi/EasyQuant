use super::ast::Expr;
use std::collections::HashMap;

/// Columnar market data for evaluation.
pub struct EvalContext {
    pub n_rows: usize,
    /// Named columns: "close", "open", "volume", etc.
    pub columns: HashMap<String, Vec<f64>>,
    /// stock_code indices: group_offsets[g] = (start, end) for contiguous stock data.
    /// If empty, treat entire array as single stock.
    pub stock_groups: Vec<(usize, usize)>,
    /// date_groups[d] = (start, end) for contiguous same-date rows.
    pub date_groups: Vec<(usize, usize)>,
}

pub fn evaluate(expr: &Expr, ctx: &EvalContext) -> Result<Vec<f64>, String> {
    match expr {
        Expr::Column(name) => {
            ctx.columns.get(name)
                .cloned()
                .ok_or_else(|| format!("column not found: {name}"))
        }
        Expr::Literal(v) => Ok(vec![*v; ctx.n_rows]),

        // Arithmetic
        Expr::Add(a, b) => bin_op(a, b, ctx, |x, y| x + y),
        Expr::Sub(a, b) => bin_op(a, b, ctx, |x, y| x - y),
        Expr::Mul(a, b) => bin_op(a, b, ctx, |x, y| x * y),
        Expr::Div(a, b) => bin_op(a, b, ctx, |x, y| if y.abs() < 1e-15 { f64::NAN } else { x / y }),
        Expr::Pow(a, b) => bin_op(a, b, ctx, |x, y| x.powf(y)),
        Expr::Neg(a) => { let v = evaluate(a, ctx)?; Ok(v.iter().map(|x| -x).collect()) }

        // Comparison
        Expr::Gt(a, b) => bin_op(a, b, ctx, |x, y| if x > y { 1.0 } else { 0.0 }),
        Expr::Lt(a, b) => bin_op(a, b, ctx, |x, y| if x < y { 1.0 } else { 0.0 }),
        Expr::Ge(a, b) => bin_op(a, b, ctx, |x, y| if x >= y { 1.0 } else { 0.0 }),
        Expr::Le(a, b) => bin_op(a, b, ctx, |x, y| if x <= y { 1.0 } else { 0.0 }),
        Expr::Eq(a, b) => bin_op(a, b, ctx, |x, y| if (x - y).abs() < 1e-12 { 1.0 } else { 0.0 }),
        Expr::Ne(a, b) => bin_op(a, b, ctx, |x, y| if (x - y).abs() >= 1e-12 { 1.0 } else { 0.0 }),
        Expr::And(a, b) => bin_op(a, b, ctx, |x, y| if x != 0.0 && y != 0.0 { 1.0 } else { 0.0 }),
        Expr::Or(a, b) => bin_op(a, b, ctx, |x, y| if x != 0.0 || y != 0.0 { 1.0 } else { 0.0 }),

        // Unary element-wise
        Expr::Log(a) => { let v = evaluate(a, ctx)?; Ok(v.iter().map(|x| x.max(1e-10).ln()).collect()) }
        Expr::Abs(a) => { let v = evaluate(a, ctx)?; Ok(v.iter().map(|x| x.abs()).collect()) }
        Expr::Sign(a) => { let v = evaluate(a, ctx)?; Ok(v.iter().map(|x| x.signum()).collect()) }
        Expr::Tanh(a) => { let v = evaluate(a, ctx)?; Ok(v.iter().map(|x| x.tanh()).collect()) }
        Expr::Sigmoid(a) => { let v = evaluate(a, ctx)?; Ok(v.iter().map(|x| 1.0 / (1.0 + (-x.clamp(-500.0, 500.0)).exp())).collect()) }
        Expr::Exp(a) => { let v = evaluate(a, ctx)?; Ok(v.iter().map(|x| x.min(500.0).exp()).collect()) }
        Expr::Sqrt(a) => { let v = evaluate(a, ctx)?; Ok(v.iter().map(|x| x.max(0.0).sqrt()).collect()) }
        Expr::Scale(a) => {
            let v = evaluate(a, ctx)?;
            let mn = v.iter().copied().filter(|x| x.is_finite()).fold(f64::INFINITY, f64::min);
            let mx = v.iter().copied().filter(|x| x.is_finite()).fold(f64::NEG_INFINITY, f64::max);
            let range = mx - mn + 1e-10;
            Ok(v.iter().map(|x| (x - mn) / range).collect())
        }

        // Cross-sectional
        Expr::Rank(a) => {
            let v = evaluate(a, ctx)?;
            cross_sectional_rank(&v, &ctx.date_groups)
        }
        Expr::Zscore(a) => {
            let v = evaluate(a, ctx)?;
            cross_sectional_zscore(&v, &ctx.date_groups)
        }

        // Time-series
        Expr::TsMean(a, w) => ts_op(a, *w, ctx, rolling_mean),
        Expr::TsStd(a, w) => ts_op(a, *w, ctx, rolling_std),
        Expr::TsMax(a, w) => ts_op(a, *w, ctx, rolling_max),
        Expr::TsMin(a, w) => ts_op(a, *w, ctx, rolling_min),
        Expr::TsSum(a, w) => ts_op(a, *w, ctx, rolling_sum),
        Expr::TsShift(a, w) => ts_op(a, *w, ctx, ts_shift),
        Expr::TsDelta(a, w) => ts_op(a, *w, ctx, ts_delta),
        Expr::TsRank(a, w) => ts_op(a, *w, ctx, ts_rank),
        Expr::TsArgmax(a, w) => ts_op(a, *w, ctx, ts_argmax),
        Expr::TsArgmin(a, w) => ts_op(a, *w, ctx, ts_argmin),
        Expr::DecayLinear(a, w) => ts_op(a, *w, ctx, decay_linear),
        Expr::Product(a, w) => ts_op(a, *w, ctx, rolling_product),
        Expr::TsAvDiff(a, w) => ts_op(a, *w, ctx, ts_av_diff),
        Expr::TsZscore(a, w) => ts_op(a, *w, ctx, ts_zscore),
        Expr::Ema(a, w) => ts_op(a, *w, ctx, ema),
        Expr::Rsi(a, w) => ts_op(a, *w, ctx, rsi),
        Expr::Macd(a, w) => ts_op(a, *w, ctx, macd),
        Expr::BollUpper(a, w) => ts_op(a, *w, ctx, boll_upper),
        Expr::BollLower(a, w) => ts_op(a, *w, ctx, boll_lower),
        Expr::BollMid(a, w) => ts_op(a, *w, ctx, rolling_mean),

        // Dual time-series
        Expr::TsCorr(a, b, w) => ts_dual_op(a, b, *w, ctx, rolling_corr),
        Expr::TsCov(a, b, w) => ts_dual_op(a, b, *w, ctx, rolling_cov),

        // Binary element-wise
        Expr::Power(a, b) => bin_op(a, b, ctx, |x, y| x.powf(y)),
        Expr::SignPower(a, b) => bin_op(a, b, ctx, |x, y| x.signum() * x.abs().powf(y)),
        Expr::Max(a, b) => bin_op(a, b, ctx, f64::max),
        Expr::Min(a, b) => bin_op(a, b, ctx, f64::min),

        // Ternary
        Expr::Where(cond, t, f) => {
            let c = evaluate(cond, ctx)?;
            let tv = evaluate(t, ctx)?;
            let fv = evaluate(f, ctx)?;
            Ok((0..ctx.n_rows).map(|i| if c[i] != 0.0 && c[i].is_finite() { tv[i] } else { fv[i] }).collect())
        }
        Expr::Clip(a, lo, hi) => {
            let v = evaluate(a, ctx)?;
            let l = evaluate(lo, ctx)?;
            let h = evaluate(hi, ctx)?;
            Ok((0..ctx.n_rows).map(|i| v[i].clamp(l[i], h[i])).collect())
        }
    }
}

// ── Helpers ─────────────────────────────────────────────────────────

fn bin_op(a: &Expr, b: &Expr, ctx: &EvalContext, op: fn(f64, f64) -> f64) -> Result<Vec<f64>, String> {
    let va = evaluate(a, ctx)?;
    let vb = evaluate(b, ctx)?;
    Ok(va.iter().zip(vb.iter()).map(|(x, y)| op(*x, *y)).collect())
}

// ── Cross-sectional ─────────────────────────────────────────────────

fn cross_sectional_rank(data: &[f64], date_groups: &[(usize, usize)]) -> Result<Vec<f64>, String> {
    let mut out = vec![f64::NAN; data.len()];
    for &(start, end) in date_groups {
        let n = end - start;
        if n == 0 { continue; }
        let mut indices: Vec<usize> = (0..n).filter(|&i| data[start + i].is_finite()).collect();
        indices.sort_by(|&a, &b| data[start + a].partial_cmp(&data[start + b]).unwrap_or(std::cmp::Ordering::Equal));
        let count = indices.len() as f64;
        if count < 1.0 { continue; }
        for (rank, &idx) in indices.iter().enumerate() {
            out[start + idx] = rank as f64 / (count - 1.0).max(1.0);
        }
    }
    Ok(out)
}

fn cross_sectional_zscore(data: &[f64], date_groups: &[(usize, usize)]) -> Result<Vec<f64>, String> {
    let mut out = vec![f64::NAN; data.len()];
    for &(start, end) in date_groups {
        let vals: Vec<f64> = (start..end).filter_map(|i| {
            if data[i].is_finite() { Some(data[i]) } else { None }
        }).collect();
        let n = vals.len() as f64;
        if n < 2.0 { continue; }
        let mean = vals.iter().sum::<f64>() / n;
        let std = (vals.iter().map(|v| (v - mean).powi(2)).sum::<f64>() / (n - 1.0)).sqrt() + 1e-10;
        for i in start..end {
            if data[i].is_finite() {
                out[i] = (data[i] - mean) / std;
            }
        }
    }
    Ok(out)
}

// ── Time-series operators (per-stock) ───────────────────────────────

fn ts_op(expr: &Expr, window: usize, ctx: &EvalContext, op: fn(&[f64], usize, &mut [f64])) -> Result<Vec<f64>, String> {
    let data = evaluate(expr, ctx)?;
    let mut out = vec![f64::NAN; ctx.n_rows];
    if ctx.stock_groups.is_empty() {
        op(&data, window, &mut out);
    } else {
        for &(start, end) in &ctx.stock_groups {
            op(&data[start..end], window, &mut out[start..end]);
        }
    }
    Ok(out)
}

fn ts_dual_op(a: &Expr, b: &Expr, window: usize, ctx: &EvalContext, op: fn(&[f64], &[f64], usize, &mut [f64])) -> Result<Vec<f64>, String> {
    let va = evaluate(a, ctx)?;
    let vb = evaluate(b, ctx)?;
    let mut out = vec![f64::NAN; ctx.n_rows];
    if ctx.stock_groups.is_empty() {
        op(&va, &vb, window, &mut out);
    } else {
        for &(start, end) in &ctx.stock_groups {
            op(&va[start..end], &vb[start..end], window, &mut out[start..end]);
        }
    }
    Ok(out)
}

// ── Rolling window implementations ─────────────────────────────────

fn rolling_mean(data: &[f64], w: usize, out: &mut [f64]) {
    let n = data.len();
    let mut sum = 0.0;
    let mut count = 0usize;
    for i in 0..n {
        if data[i].is_finite() { sum += data[i]; count += 1; }
        if i >= w {
            if data[i - w].is_finite() { sum -= data[i - w]; count -= 1; }
        }
        out[i] = if count > 0 { sum / count as f64 } else { f64::NAN };
    }
}

fn rolling_sum(data: &[f64], w: usize, out: &mut [f64]) {
    let n = data.len();
    let mut sum = 0.0;
    let mut count = 0usize;
    for i in 0..n {
        if data[i].is_finite() { sum += data[i]; count += 1; }
        if i >= w {
            if data[i - w].is_finite() { sum -= data[i - w]; count -= 1; }
        }
        out[i] = if count > 0 { sum } else { f64::NAN };
    }
}

fn rolling_std(data: &[f64], w: usize, out: &mut [f64]) {
    let n = data.len();
    for i in 0..n {
        let start = if i >= w { i - w + 1 } else { 0 };
        let vals: Vec<f64> = data[start..=i].iter().copied().filter(|v| v.is_finite()).collect();
        if vals.len() < 2 {
            out[i] = f64::NAN;
            continue;
        }
        let mean = vals.iter().sum::<f64>() / vals.len() as f64;
        let var = vals.iter().map(|v| (v - mean).powi(2)).sum::<f64>() / (vals.len() - 1) as f64;
        out[i] = var.sqrt();
    }
}

fn rolling_max(data: &[f64], w: usize, out: &mut [f64]) {
    let n = data.len();
    for i in 0..n {
        let start = if i >= w { i - w + 1 } else { 0 };
        let mx = data[start..=i].iter().copied().filter(|v| v.is_finite()).fold(f64::NEG_INFINITY, f64::max);
        out[i] = if mx == f64::NEG_INFINITY { f64::NAN } else { mx };
    }
}

fn rolling_min(data: &[f64], w: usize, out: &mut [f64]) {
    let n = data.len();
    for i in 0..n {
        let start = if i >= w { i - w + 1 } else { 0 };
        let mn = data[start..=i].iter().copied().filter(|v| v.is_finite()).fold(f64::INFINITY, f64::min);
        out[i] = if mn == f64::INFINITY { f64::NAN } else { mn };
    }
}

fn ts_shift(data: &[f64], w: usize, out: &mut [f64]) {
    for i in 0..data.len() {
        out[i] = if i >= w { data[i - w] } else { f64::NAN };
    }
}

fn ts_delta(data: &[f64], w: usize, out: &mut [f64]) {
    for i in 0..data.len() {
        out[i] = if i >= w { data[i] - data[i - w] } else { f64::NAN };
    }
}

fn ts_rank(data: &[f64], w: usize, out: &mut [f64]) {
    let n = data.len();
    for i in 0..n {
        let start = if i >= w { i - w + 1 } else { 0 };
        let cur = data[i];
        if !cur.is_finite() { out[i] = f64::NAN; continue; }
        let vals: Vec<f64> = data[start..=i].iter().copied().filter(|v| v.is_finite()).collect();
        if vals.is_empty() { out[i] = f64::NAN; continue; }
        let rank = vals.iter().filter(|&&v| v <= cur).count();
        out[i] = rank as f64 / vals.len() as f64;
    }
}

fn ts_argmax(data: &[f64], w: usize, out: &mut [f64]) {
    let n = data.len();
    for i in 0..n {
        let start = if i >= w { i - w + 1 } else { 0 };
        let mut best_idx = 0usize;
        let mut best_val = f64::NEG_INFINITY;
        for (j, &v) in data[start..=i].iter().enumerate() {
            if v.is_finite() && v > best_val { best_val = v; best_idx = j; }
        }
        out[i] = if best_val == f64::NEG_INFINITY { f64::NAN } else { best_idx as f64 };
    }
}

fn ts_argmin(data: &[f64], w: usize, out: &mut [f64]) {
    let n = data.len();
    for i in 0..n {
        let start = if i >= w { i - w + 1 } else { 0 };
        let mut best_idx = 0usize;
        let mut best_val = f64::INFINITY;
        for (j, &v) in data[start..=i].iter().enumerate() {
            if v.is_finite() && v < best_val { best_val = v; best_idx = j; }
        }
        out[i] = if best_val == f64::INFINITY { f64::NAN } else { best_idx as f64 };
    }
}

fn decay_linear(data: &[f64], w: usize, out: &mut [f64]) {
    let weights: Vec<f64> = (1..=w).map(|i| i as f64).collect();
    let _wsum: f64 = weights.iter().sum();
    let n = data.len();
    for i in 0..n {
        let start = if i >= w { i - w + 1 } else { 0 };
        let slice = &data[start..=i];
        let offset = w.saturating_sub(slice.len());
        let mut numer = 0.0;
        let mut denom = 0.0;
        for (j, &v) in slice.iter().enumerate() {
            if v.is_finite() {
                let wt = weights[offset + j];
                numer += v * wt;
                denom += wt;
            }
        }
        out[i] = if denom > 0.0 { numer / denom } else { f64::NAN };
    }
}

fn rolling_product(data: &[f64], w: usize, out: &mut [f64]) {
    let n = data.len();
    for i in 0..n {
        let start = if i >= w { i - w + 1 } else { 0 };
        let mut prod = 1.0;
        let mut any = false;
        for &v in &data[start..=i] {
            if v.is_finite() { prod *= v; any = true; }
        }
        out[i] = if any { prod } else { f64::NAN };
    }
}

fn ts_av_diff(data: &[f64], w: usize, out: &mut [f64]) {
    let mut means = vec![f64::NAN; data.len()];
    rolling_mean(data, w, &mut means);
    for i in 0..data.len() {
        out[i] = if data[i].is_finite() && means[i].is_finite() { data[i] - means[i] } else { f64::NAN };
    }
}

fn ts_zscore(data: &[f64], w: usize, out: &mut [f64]) {
    let mut means = vec![f64::NAN; data.len()];
    let mut stds = vec![f64::NAN; data.len()];
    rolling_mean(data, w, &mut means);
    rolling_std(data, w, &mut stds);
    for i in 0..data.len() {
        if data[i].is_finite() && means[i].is_finite() && stds[i].is_finite() {
            out[i] = (data[i] - means[i]) / (stds[i] + 1e-10);
        } else {
            out[i] = f64::NAN;
        }
    }
}

fn ema(data: &[f64], span: usize, out: &mut [f64]) {
    let alpha = 2.0 / (span as f64 + 1.0);
    let mut prev = f64::NAN;
    for i in 0..data.len() {
        if !data[i].is_finite() {
            out[i] = prev;
            continue;
        }
        if !prev.is_finite() {
            prev = data[i];
        } else {
            prev = alpha * data[i] + (1.0 - alpha) * prev;
        }
        out[i] = prev;
    }
}

fn rsi(data: &[f64], w: usize, out: &mut [f64]) {
    let n = data.len();
    if n < 2 { for o in out.iter_mut() { *o = f64::NAN; } return; }
    let alpha = 1.0 / w as f64;
    let mut avg_gain = 0.0;
    let mut avg_loss = 0.0;
    let mut started = false;
    out[0] = f64::NAN;
    for i in 1..n {
        let change = if data[i].is_finite() && data[i - 1].is_finite() { data[i] - data[i - 1] } else { 0.0 };
        let gain = change.max(0.0);
        let loss = (-change).max(0.0);
        if !started && i >= w {
            let mut sg = 0.0;
            let mut sl = 0.0;
            for j in (i - w + 1)..=i {
                let c = if data[j].is_finite() && data[j - 1].is_finite() { data[j] - data[j - 1] } else { 0.0 };
                sg += c.max(0.0);
                sl += (-c).max(0.0);
            }
            avg_gain = sg / w as f64;
            avg_loss = sl / w as f64;
            started = true;
        } else if started {
            avg_gain = alpha * gain + (1.0 - alpha) * avg_gain;
            avg_loss = alpha * loss + (1.0 - alpha) * avg_loss;
        }
        if started {
            let rs = if avg_loss < 1e-15 { 100.0 } else { avg_gain / avg_loss };
            out[i] = 100.0 - 100.0 / (1.0 + rs);
        } else {
            out[i] = f64::NAN;
        }
    }
}

fn macd(data: &[f64], w: usize, out: &mut [f64]) {
    let fast_span = (w / 2).max(1);
    let slow_span = w;
    let sig_span = (w / 4).max(1);
    let mut fast = vec![f64::NAN; data.len()];
    let mut slow = vec![f64::NAN; data.len()];
    ema(data, fast_span, &mut fast);
    ema(data, slow_span, &mut slow);
    let macd_line: Vec<f64> = fast.iter().zip(slow.iter()).map(|(f, s)| f - s).collect();
    let mut signal = vec![f64::NAN; data.len()];
    ema(&macd_line, sig_span, &mut signal);
    for i in 0..data.len() {
        out[i] = macd_line[i] - signal[i];
    }
}

fn boll_upper(data: &[f64], w: usize, out: &mut [f64]) {
    let mut means = vec![f64::NAN; data.len()];
    let mut stds = vec![f64::NAN; data.len()];
    rolling_mean(data, w, &mut means);
    rolling_std(data, w, &mut stds);
    for i in 0..data.len() {
        out[i] = means[i] + 2.0 * stds[i];
    }
}

fn boll_lower(data: &[f64], w: usize, out: &mut [f64]) {
    let mut means = vec![f64::NAN; data.len()];
    let mut stds = vec![f64::NAN; data.len()];
    rolling_mean(data, w, &mut means);
    rolling_std(data, w, &mut stds);
    for i in 0..data.len() {
        out[i] = means[i] - 2.0 * stds[i];
    }
}

// ── Dual rolling ────────────────────────────────────────────────────

fn rolling_corr(a: &[f64], b: &[f64], w: usize, out: &mut [f64]) {
    let n = a.len();
    for i in 0..n {
        let start = if i >= w { i - w + 1 } else { 0 };
        let pairs: Vec<(f64, f64)> = a[start..=i].iter().zip(b[start..=i].iter())
            .filter(|(&x, &y)| x.is_finite() && y.is_finite())
            .map(|(&x, &y)| (x, y))
            .collect();
        if pairs.len() < 3 { out[i] = f64::NAN; continue; }
        let n_f = pairs.len() as f64;
        let mx = pairs.iter().map(|(x, _)| x).sum::<f64>() / n_f;
        let my = pairs.iter().map(|(_, y)| y).sum::<f64>() / n_f;
        let mut cov = 0.0;
        let mut vx = 0.0;
        let mut vy = 0.0;
        for &(x, y) in &pairs {
            cov += (x - mx) * (y - my);
            vx += (x - mx).powi(2);
            vy += (y - my).powi(2);
        }
        let denom = (vx * vy).sqrt();
        out[i] = if denom < 1e-15 { f64::NAN } else { cov / denom };
    }
}

fn rolling_cov(a: &[f64], b: &[f64], w: usize, out: &mut [f64]) {
    let n = a.len();
    for i in 0..n {
        let start = if i >= w { i - w + 1 } else { 0 };
        let pairs: Vec<(f64, f64)> = a[start..=i].iter().zip(b[start..=i].iter())
            .filter(|(&x, &y)| x.is_finite() && y.is_finite())
            .map(|(&x, &y)| (x, y))
            .collect();
        if pairs.len() < 2 { out[i] = f64::NAN; continue; }
        let n_f = pairs.len() as f64;
        let mx = pairs.iter().map(|(x, _)| x).sum::<f64>() / n_f;
        let my = pairs.iter().map(|(_, y)| y).sum::<f64>() / n_f;
        let cov = pairs.iter().map(|(x, y)| (x - mx) * (y - my)).sum::<f64>() / (n_f - 1.0);
        out[i] = cov;
    }
}
