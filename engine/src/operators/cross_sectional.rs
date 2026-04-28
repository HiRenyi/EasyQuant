use rayon::prelude::*;

/// Parallel cross-sectional rank (0–1 percentile) by date groups.
pub fn par_rank(data: &[f64], date_groups: &[(usize, usize)]) -> Vec<f64> {
    let mut out = vec![f64::NAN; data.len()];
    let chunks: Vec<_> = date_groups.iter().map(|&(s, e)| (s, e)).collect();
    let results: Vec<Vec<(usize, f64)>> = chunks.par_iter().map(|&(start, end)| {
        let mut indices: Vec<usize> = (0..end - start)
            .filter(|&i| data[start + i].is_finite())
            .collect();
        indices.sort_by(|&a, &b| {
            data[start + a].partial_cmp(&data[start + b]).unwrap_or(std::cmp::Ordering::Equal)
        });
        let count = indices.len() as f64;
        if count < 1.0 { return vec![]; }
        indices.iter().enumerate().map(|(rank, &idx)| {
            (start + idx, rank as f64 / (count - 1.0).max(1.0))
        }).collect()
    }).collect();

    for group in results {
        for (idx, val) in group {
            out[idx] = val;
        }
    }
    out
}

/// Parallel cross-sectional zscore by date groups.
pub fn par_zscore(data: &[f64], date_groups: &[(usize, usize)]) -> Vec<f64> {
    let mut out = vec![f64::NAN; data.len()];
    let results: Vec<Vec<(usize, f64)>> = date_groups.par_iter().map(|&(start, end)| {
        let vals: Vec<f64> = (start..end)
            .filter_map(|i| if data[i].is_finite() { Some(data[i]) } else { None })
            .collect();
        let n = vals.len() as f64;
        if n < 2.0 { return vec![]; }
        let mean = vals.iter().sum::<f64>() / n;
        let std = (vals.iter().map(|v| (v - mean).powi(2)).sum::<f64>() / (n - 1.0)).sqrt() + 1e-10;
        (start..end).filter_map(|i| {
            if data[i].is_finite() { Some((i, (data[i] - mean) / std)) } else { None }
        }).collect()
    }).collect();

    for group in results {
        for (idx, val) in group {
            out[idx] = val;
        }
    }
    out
}
