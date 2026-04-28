use ordered_float::OrderedFloat;

/// Assign stocks to quantile groups based on factor values.
/// Returns group assignment (0..n_groups-1) for each stock. NaN factor → group = usize::MAX.
pub fn assign_groups(factor_values: &[f64], n_groups: usize) -> Vec<usize> {
    let n = factor_values.len();
    let mut assignments = vec![usize::MAX; n];

    let valid: Vec<(usize, f64)> = factor_values.iter().enumerate()
        .filter(|(_, &v)| v.is_finite())
        .map(|(i, &v)| (i, v))
        .collect();

    if valid.is_empty() { return assignments; }

    // Count distinct values
    let mut distinct: Vec<OrderedFloat<f64>> = valid.iter().map(|(_, v)| OrderedFloat(*v)).collect();
    distinct.sort();
    distinct.dedup();
    let n_distinct = distinct.len();

    let actual_groups = n_groups.min(n_distinct);
    if actual_groups < 2 {
        for (i, _) in &valid { assignments[*i] = 0; }
        return assignments;
    }

    if n_distinct <= n_groups {
        // Value-based grouping: each unique value → one group
        let val_to_group: std::collections::HashMap<OrderedFloat<f64>, usize> =
            distinct.iter().enumerate().map(|(g, &v)| (v, g)).collect();
        for &(i, v) in &valid {
            assignments[i] = val_to_group[&OrderedFloat(v)];
        }
    } else {
        // Rank-based quantile grouping
        let mut sorted = valid.clone();
        sorted.sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(std::cmp::Ordering::Equal));
        let count = sorted.len();
        for (rank, &(idx, _)) in sorted.iter().enumerate() {
            let group = (rank * actual_groups / count).min(actual_groups - 1);
            assignments[idx] = group;
        }
    }

    assignments
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_basic_grouping() {
        let vals = vec![1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0];
        let groups = assign_groups(&vals, 5);
        assert!(groups.iter().all(|&g| g < 5));
        // Lowest values should be in group 0
        assert_eq!(groups[0], 0);
        assert_eq!(groups[1], 0);
        // Highest values in group 4
        assert_eq!(groups[8], 4);
        assert_eq!(groups[9], 4);
    }

    #[test]
    fn test_nan_handling() {
        let vals = vec![1.0, f64::NAN, 3.0, 4.0, f64::NAN];
        let groups = assign_groups(&vals, 3);
        assert_eq!(groups[1], usize::MAX);
        assert_eq!(groups[4], usize::MAX);
        assert!(groups[0] < 3);
    }
}
