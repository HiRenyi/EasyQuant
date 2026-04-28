mod expression;
mod operators;
mod backtest;

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use numpy::{PyArray1, PyReadonlyArray1};
use std::collections::HashMap;

use expression::parser::parse;
use expression::eval::{evaluate, EvalContext};
use backtest::engine::run_backtest;
use backtest::metrics;

/// Parse and evaluate a factor expression on columnar data.
///
/// Args:
///     expression: Factor expression string (e.g., "rank(close / vwap)")
///     columns: dict[str, numpy.ndarray[f64]] — named columns
///     stock_offsets: list[(int, int)] — (start, end) for each stock's contiguous block
///     date_offsets: list[(int, int)] — (start, end) for each date's contiguous block
///
/// Returns:
///     numpy.ndarray[f64] — factor values (same length as input columns)
#[pyfunction]
fn eval_expression<'py>(
    py: Python<'py>,
    expression: &str,
    columns: &Bound<'py, PyDict>,
    stock_offsets: Vec<(usize, usize)>,
    date_offsets: Vec<(usize, usize)>,
) -> PyResult<Bound<'py, PyArray1<f64>>> {
    let ast = parse(expression)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e))?;

    let mut col_map: HashMap<String, Vec<f64>> = HashMap::new();
    let mut n_rows = 0usize;
    for (key, val) in columns.iter() {
        let name: String = key.extract()?;
        let arr: PyReadonlyArray1<f64> = val.extract()?;
        let slice = arr.as_slice()?;
        n_rows = slice.len();
        col_map.insert(name, slice.to_vec());
    }

    let ctx = EvalContext {
        n_rows,
        columns: col_map,
        stock_groups: stock_offsets,
        date_groups: date_offsets,
    };

    let result = evaluate(&ast, &ctx)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e))?;

    Ok(PyArray1::from_vec(py, result))
}

/// Parse an expression and return a string representation (for validation).
#[pyfunction]
fn parse_expression_ast(expression: &str) -> PyResult<String> {
    let ast = parse(expression)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e))?;
    Ok(format!("{ast:?}"))
}

/// Run the full quantile-group backtest.
///
/// Args:
///     dates: numpy.ndarray[i64] — trade dates as epoch days
///     stock_codes: list[str] — stock code per row
///     factor_values: numpy.ndarray[f64] — pre-computed factor values
///     daily_returns: numpy.ndarray[f64] — daily return per row
///     n_groups: int
///     holding_period: int
///     cost_rate: float
///     trading_days_per_year: float
///
/// Returns:
///     dict with backtest results
#[pyfunction]
fn run_factor_backtest<'py>(
    py: Python<'py>,
    dates: PyReadonlyArray1<'py, i64>,
    stock_codes: Vec<String>,
    factor_values: PyReadonlyArray1<'py, f64>,
    daily_returns: PyReadonlyArray1<'py, f64>,
    n_groups: usize,
    holding_period: usize,
    cost_rate: f64,
    trading_days_per_year: f64,
) -> PyResult<Bound<'py, PyDict>> {
    let d = dates.as_slice()?;
    let fv = factor_values.as_slice()?;
    let dr = daily_returns.as_slice()?;

    let result = run_backtest(d, &stock_codes, fv, dr, n_groups, holding_period, cost_rate, trading_days_per_year);

    let dict = PyDict::new(py);

    // Strategy returns
    dict.set_item("strategy_returns", PyArray1::from_vec(py, result.strategy_returns))?;
    dict.set_item("ls_returns", PyArray1::from_vec(py, result.ls_returns))?;

    // Scalars
    dict.set_item("long_short_sharpe", result.long_short_sharpe)?;
    dict.set_item("long_short_annual", result.long_short_annual)?;
    dict.set_item("top_group_sharpe", result.top_group_sharpe)?;
    dict.set_item("monotonicity_score", result.monotonicity_score)?;
    dict.set_item("spread", result.spread)?;
    dict.set_item("flipped", result.flipped)?;
    dict.set_item("ic_mean", result.ic_mean)?;
    dict.set_item("rank_ic_mean", result.rank_ic_mean)?;
    dict.set_item("ic_ir", result.ic_ir)?;
    dict.set_item("ic_win_rate", result.ic_win_rate)?;
    dict.set_item("turnover", result.turnover)?;
    dict.set_item("wq_fitness", result.wq_fitness)?;
    dict.set_item("cost_adjusted", result.cost_adjusted)?;
    dict.set_item("cost_rate", result.cost_rate)?;
    dict.set_item("total_cost_drag", result.total_cost_drag)?;

    // Group returns
    let groups = PyDict::new(py);
    for (i, gs) in result.group_stats.iter().enumerate() {
        let gd = PyDict::new(py);
        gd.set_item("group", &gs.group)?;
        gd.set_item("mean_return", gs.mean_return)?;
        gd.set_item("annual_return", gs.annual_return)?;
        gd.set_item("sharpe", gs.sharpe)?;
        gd.set_item("max_drawdown", gs.max_drawdown)?;
        groups.set_item(i, gd)?;
    }
    dict.set_item("group_returns", groups)?;

    // Factor DF arrays for WQ simulate
    dict.set_item("_factor_dates", PyArray1::from_vec(py, result.factor_df_dates))?;
    dict.set_item("_factor_stocks", PyList::new(py, &result.factor_df_stocks)?)?;
    dict.set_item("_factor_values", PyArray1::from_vec(py, result.factor_df_values))?;
    dict.set_item("_factor_returns", PyArray1::from_vec(py, result.factor_df_returns))?;

    Ok(dict)
}

/// Compute standard performance metrics on a return series.
#[pyfunction]
fn compute_metrics<'py>(
    py: Python<'py>,
    daily_returns: PyReadonlyArray1<'py, f64>,
    periods_per_year: f64,
) -> PyResult<Bound<'py, PyDict>> {
    let rets = daily_returns.as_slice()?;
    let dict = PyDict::new(py);
    let total: f64 = rets.iter().map(|r| 1.0 + r).product::<f64>() - 1.0;
    dict.set_item("total_return", total)?;
    dict.set_item("cagr", metrics::annual_return(rets, periods_per_year))?;
    dict.set_item("sharpe", metrics::sharpe(rets, periods_per_year))?;
    dict.set_item("sortino", metrics::sortino(rets, periods_per_year))?;
    dict.set_item("max_drawdown", metrics::max_drawdown(rets))?;
    dict.set_item("volatility", metrics::volatility(rets, periods_per_year))?;
    dict.set_item("win_rate", metrics::win_rate(rets))?;
    dict.set_item("profit_factor", metrics::profit_factor(rets))?;
    Ok(dict)
}

#[pymodule]
fn quantgpt_engine(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(eval_expression, m)?)?;
    m.add_function(wrap_pyfunction!(parse_expression_ast, m)?)?;
    m.add_function(wrap_pyfunction!(run_factor_backtest, m)?)?;
    m.add_function(wrap_pyfunction!(compute_metrics, m)?)?;
    Ok(())
}
