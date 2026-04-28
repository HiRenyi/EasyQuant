use rayon::prelude::*;

/// Apply a per-stock time-series operation in parallel across stocks.
pub fn par_ts_op(
    data: &[f64],
    stock_groups: &[(usize, usize)],
    window: usize,
    op: fn(&[f64], usize, &mut [f64]),
) -> Vec<f64> {
    let mut out = vec![f64::NAN; data.len()];
    if stock_groups.is_empty() {
        op(data, window, &mut out);
        return out;
    }

    let results: Vec<(usize, Vec<f64>)> = stock_groups.par_iter().map(|&(start, end)| {
        let mut buf = vec![f64::NAN; end - start];
        op(&data[start..end], window, &mut buf);
        (start, buf)
    }).collect();

    for (start, buf) in results {
        out[start..start + buf.len()].copy_from_slice(&buf);
    }
    out
}

/// Apply a dual-column per-stock time-series operation in parallel.
pub fn par_ts_dual_op(
    a: &[f64],
    b: &[f64],
    stock_groups: &[(usize, usize)],
    window: usize,
    op: fn(&[f64], &[f64], usize, &mut [f64]),
) -> Vec<f64> {
    let mut out = vec![f64::NAN; a.len()];
    if stock_groups.is_empty() {
        op(a, b, window, &mut out);
        return out;
    }

    let results: Vec<(usize, Vec<f64>)> = stock_groups.par_iter().map(|&(start, end)| {
        let mut buf = vec![f64::NAN; end - start];
        op(&a[start..end], &b[start..end], window, &mut buf);
        (start, buf)
    }).collect();

    for (start, buf) in results {
        out[start..start + buf.len()].copy_from_slice(&buf);
    }
    out
}
