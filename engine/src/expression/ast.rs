/// Factor expression AST.
///
/// Every node evaluates to a 1-D f64 array aligned to the input DataFrame rows.

#[derive(Debug, Clone)]
pub enum Expr {
    /// Raw column reference: "close", "volume", "vwap", etc.
    Column(String),

    /// Numeric literal: 2.0, 0.5, etc.
    Literal(f64),

    // ── Arithmetic ──────────────────────────────────────────────

    Add(Box<Expr>, Box<Expr>),
    Sub(Box<Expr>, Box<Expr>),
    Mul(Box<Expr>, Box<Expr>),
    Div(Box<Expr>, Box<Expr>),
    Pow(Box<Expr>, Box<Expr>),
    Neg(Box<Expr>),

    // ── Comparison / Logic ──────────────────────────────────────

    Gt(Box<Expr>, Box<Expr>),
    Lt(Box<Expr>, Box<Expr>),
    Ge(Box<Expr>, Box<Expr>),
    Le(Box<Expr>, Box<Expr>),
    Eq(Box<Expr>, Box<Expr>),
    Ne(Box<Expr>, Box<Expr>),
    And(Box<Expr>, Box<Expr>),
    Or(Box<Expr>, Box<Expr>),

    // ── Unary element-wise ──────────────────────────────────────

    Log(Box<Expr>),
    Abs(Box<Expr>),
    Sign(Box<Expr>),
    Scale(Box<Expr>),
    Tanh(Box<Expr>),
    Sigmoid(Box<Expr>),
    Exp(Box<Expr>),
    Sqrt(Box<Expr>),

    // ── Cross-sectional (grouped by date) ───────────────────────

    Rank(Box<Expr>),
    Zscore(Box<Expr>),

    // ── Time-series (per stock, rolling window) ─────────────────

    TsMean(Box<Expr>, usize),
    TsStd(Box<Expr>, usize),
    TsMax(Box<Expr>, usize),
    TsMin(Box<Expr>, usize),
    TsSum(Box<Expr>, usize),
    TsShift(Box<Expr>, usize),
    TsDelta(Box<Expr>, usize),
    TsRank(Box<Expr>, usize),
    TsArgmax(Box<Expr>, usize),
    TsArgmin(Box<Expr>, usize),
    DecayLinear(Box<Expr>, usize),
    Product(Box<Expr>, usize),
    TsAvDiff(Box<Expr>, usize),
    TsZscore(Box<Expr>, usize),
    Ema(Box<Expr>, usize),
    Rsi(Box<Expr>, usize),
    Macd(Box<Expr>, usize),

    // ── Bollinger Band ──────────────────────────────────────────

    BollUpper(Box<Expr>, usize),
    BollLower(Box<Expr>, usize),
    BollMid(Box<Expr>, usize),

    // ── Dual time-series (two columns + window) ─────────────────

    TsCorr(Box<Expr>, Box<Expr>, usize),
    TsCov(Box<Expr>, Box<Expr>, usize),

    // ── Binary element-wise ─────────────────────────────────────

    Power(Box<Expr>, Box<Expr>),
    SignPower(Box<Expr>, Box<Expr>),
    Max(Box<Expr>, Box<Expr>),
    Min(Box<Expr>, Box<Expr>),

    // ── Ternary / Control ───────────────────────────────────────

    Where(Box<Expr>, Box<Expr>, Box<Expr>),
    Clip(Box<Expr>, Box<Expr>, Box<Expr>),
}
