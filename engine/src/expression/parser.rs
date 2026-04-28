use super::ast::Expr;
use std::collections::HashMap;

const MAX_DEPTH: usize = 100;
const MAX_WINDOW: usize = 500;

/// Operator alias table (Alpha101 compat).
fn aliases() -> HashMap<&'static str, &'static str> {
    [
        ("delta", "ts_delta"),
        ("delay", "ts_shift"),
        ("ts_delay", "ts_shift"),
        ("covariance", "ts_cov"),
        ("correlation", "ts_corr"),
        ("ts_covariance", "ts_cov"),
        ("av_diff", "ts_av_diff"),
        ("stddev", "ts_std"),
        ("ts_std_dev", "ts_std"),
        ("ts_decay_linear", "decay_linear"),
        ("ts_product", "product"),
        ("ts_arg_max", "ts_argmax"),
        ("ts_arg_min", "ts_argmin"),
        ("sma", "ts_mean"),
        ("wma", "decay_linear"),
        ("pow", "power"),
    ]
    .into_iter()
    .collect()
}

pub fn parse(input: &str) -> Result<Expr, String> {
    let input = input.trim();
    if input.is_empty() {
        return Err("empty expression".into());
    }
    if input.len() > 1000 {
        return Err("expression too long (max 1000 chars)".into());
    }
    let tokens = tokenize(input)?;
    let (expr, rest) = parse_ternary(&tokens, 0)?;
    if rest < tokens.len() {
        return Err(format!("unexpected token at position {rest}: {:?}", tokens[rest]));
    }
    Ok(expr)
}

// ── Tokenizer ───────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
enum Token {
    Ident(String),
    Num(f64),
    LParen,
    RParen,
    Comma,
    Plus,
    Minus,
    Star,
    Slash,
    Caret,
    Gt,
    Lt,
    Ge,
    Le,
    EqEq,
    Ne,
    And,
    Or,
    If,
    Else,
    Question,
    Colon,
}

fn tokenize(input: &str) -> Result<Vec<Token>, String> {
    let mut tokens = Vec::new();
    let chars: Vec<char> = input.chars().collect();
    let mut i = 0;
    while i < chars.len() {
        match chars[i] {
            ' ' | '\t' | '\n' | '\r' => i += 1,
            '(' => { tokens.push(Token::LParen); i += 1; }
            ')' => { tokens.push(Token::RParen); i += 1; }
            ',' => { tokens.push(Token::Comma); i += 1; }
            '+' => { tokens.push(Token::Plus); i += 1; }
            '-' => { tokens.push(Token::Minus); i += 1; }
            '*' => { tokens.push(Token::Star); i += 1; }
            '/' => { tokens.push(Token::Slash); i += 1; }
            '^' => { tokens.push(Token::Caret); i += 1; }
            '?' => { tokens.push(Token::Question); i += 1; }
            ':' => { tokens.push(Token::Colon); i += 1; }
            '>' if i + 1 < chars.len() && chars[i + 1] == '=' => {
                tokens.push(Token::Ge); i += 2;
            }
            '>' => { tokens.push(Token::Gt); i += 1; }
            '<' if i + 1 < chars.len() && chars[i + 1] == '=' => {
                tokens.push(Token::Le); i += 2;
            }
            '<' => { tokens.push(Token::Lt); i += 1; }
            '=' if i + 1 < chars.len() && chars[i + 1] == '=' => {
                tokens.push(Token::EqEq); i += 2;
            }
            '!' if i + 1 < chars.len() && chars[i + 1] == '=' => {
                tokens.push(Token::Ne); i += 2;
            }
            '&' if i + 1 < chars.len() && chars[i + 1] == '&' => {
                tokens.push(Token::And); i += 2;
            }
            '&' => { tokens.push(Token::And); i += 1; }
            '|' if i + 1 < chars.len() && chars[i + 1] == '|' => {
                tokens.push(Token::Or); i += 2;
            }
            '|' => { tokens.push(Token::Or); i += 1; }
            c if c.is_ascii_digit() || c == '.' => {
                let start = i;
                while i < chars.len() && (chars[i].is_ascii_digit() || chars[i] == '.') {
                    i += 1;
                }
                let s: String = chars[start..i].iter().collect();
                let n: f64 = s.parse().map_err(|_| format!("invalid number: {s}"))?;
                tokens.push(Token::Num(n));
            }
            c if c.is_ascii_alphabetic() || c == '_' => {
                let start = i;
                while i < chars.len() && (chars[i].is_ascii_alphanumeric() || chars[i] == '_') {
                    i += 1;
                }
                let s: String = chars[start..i].iter().collect();
                match s.as_str() {
                    "if" => tokens.push(Token::If),
                    "else" => tokens.push(Token::Else),
                    "and" => tokens.push(Token::And),
                    "or" => tokens.push(Token::Or),
                    _ => tokens.push(Token::Ident(s)),
                }
            }
            c => return Err(format!("unexpected character: {c}")),
        }
    }
    Ok(tokens)
}

// ── Recursive Descent Parser ────────────────────────────────────────

type PR = Result<(Expr, usize), String>;

fn parse_ternary(tokens: &[Token], pos: usize) -> PR {
    let (expr, mut pos) = parse_or(tokens, pos)?;
    // Python ternary: value if condition else alt
    if pos < tokens.len() && tokens[pos] == Token::If {
        pos += 1;
        let (cond, p) = parse_or(tokens, pos)?;
        pos = p;
        if pos >= tokens.len() || tokens[pos] != Token::Else {
            return Err("expected 'else' in ternary".into());
        }
        pos += 1;
        let (alt, p) = parse_ternary(tokens, pos)?;
        return Ok((Expr::Where(Box::new(cond), Box::new(expr), Box::new(alt)), p));
    }
    // C ternary: cond ? t : f
    if pos < tokens.len() && tokens[pos] == Token::Question {
        pos += 1;
        let (t, p) = parse_or(tokens, pos)?;
        pos = p;
        if pos >= tokens.len() || tokens[pos] != Token::Colon {
            return Err("expected ':' in ternary".into());
        }
        pos += 1;
        let (f, p) = parse_ternary(tokens, pos)?;
        return Ok((Expr::Where(Box::new(expr), Box::new(t), Box::new(f)), p));
    }
    Ok((expr, pos))
}

fn parse_or(tokens: &[Token], pos: usize) -> PR {
    let (mut left, mut pos) = parse_and(tokens, pos)?;
    while pos < tokens.len() && tokens[pos] == Token::Or {
        pos += 1;
        let (right, p) = parse_and(tokens, pos)?;
        left = Expr::Or(Box::new(left), Box::new(right));
        pos = p;
    }
    Ok((left, pos))
}

fn parse_and(tokens: &[Token], pos: usize) -> PR {
    let (mut left, mut pos) = parse_comparison(tokens, pos)?;
    while pos < tokens.len() && tokens[pos] == Token::And {
        pos += 1;
        let (right, p) = parse_comparison(tokens, pos)?;
        left = Expr::And(Box::new(left), Box::new(right));
        pos = p;
    }
    Ok((left, pos))
}

fn parse_comparison(tokens: &[Token], pos: usize) -> PR {
    let (mut left, mut pos) = parse_additive(tokens, pos)?;
    loop {
        if pos >= tokens.len() { break; }
        match &tokens[pos] {
            Token::Gt => { pos += 1; let (r, p) = parse_additive(tokens, pos)?; left = Expr::Gt(Box::new(left), Box::new(r)); pos = p; }
            Token::Lt => { pos += 1; let (r, p) = parse_additive(tokens, pos)?; left = Expr::Lt(Box::new(left), Box::new(r)); pos = p; }
            Token::Ge => { pos += 1; let (r, p) = parse_additive(tokens, pos)?; left = Expr::Ge(Box::new(left), Box::new(r)); pos = p; }
            Token::Le => { pos += 1; let (r, p) = parse_additive(tokens, pos)?; left = Expr::Le(Box::new(left), Box::new(r)); pos = p; }
            Token::EqEq => { pos += 1; let (r, p) = parse_additive(tokens, pos)?; left = Expr::Eq(Box::new(left), Box::new(r)); pos = p; }
            Token::Ne => { pos += 1; let (r, p) = parse_additive(tokens, pos)?; left = Expr::Ne(Box::new(left), Box::new(r)); pos = p; }
            _ => break,
        }
    }
    Ok((left, pos))
}

fn parse_additive(tokens: &[Token], pos: usize) -> PR {
    let (mut left, mut pos) = parse_multiplicative(tokens, pos)?;
    loop {
        if pos >= tokens.len() { break; }
        match &tokens[pos] {
            Token::Plus => { pos += 1; let (r, p) = parse_multiplicative(tokens, pos)?; left = Expr::Add(Box::new(left), Box::new(r)); pos = p; }
            Token::Minus => { pos += 1; let (r, p) = parse_multiplicative(tokens, pos)?; left = Expr::Sub(Box::new(left), Box::new(r)); pos = p; }
            _ => break,
        }
    }
    Ok((left, pos))
}

fn parse_multiplicative(tokens: &[Token], pos: usize) -> PR {
    let (mut left, mut pos) = parse_power(tokens, pos)?;
    loop {
        if pos >= tokens.len() { break; }
        match &tokens[pos] {
            Token::Star => { pos += 1; let (r, p) = parse_power(tokens, pos)?; left = Expr::Mul(Box::new(left), Box::new(r)); pos = p; }
            Token::Slash => { pos += 1; let (r, p) = parse_power(tokens, pos)?; left = Expr::Div(Box::new(left), Box::new(r)); pos = p; }
            _ => break,
        }
    }
    Ok((left, pos))
}

fn parse_power(tokens: &[Token], pos: usize) -> PR {
    let (base, mut pos) = parse_unary(tokens, pos)?;
    if pos < tokens.len() && tokens[pos] == Token::Caret {
        pos += 1;
        let (exp, p) = parse_unary(tokens, pos)?;
        return Ok((Expr::Pow(Box::new(base), Box::new(exp)), p));
    }
    Ok((base, pos))
}

fn parse_unary(tokens: &[Token], pos: usize) -> PR {
    if pos < tokens.len() && tokens[pos] == Token::Minus {
        let (inner, p) = parse_unary(tokens, pos + 1)?;
        return Ok((Expr::Neg(Box::new(inner)), p));
    }
    parse_primary(tokens, pos, 0)
}

fn parse_primary(tokens: &[Token], pos: usize, depth: usize) -> PR {
    if depth > MAX_DEPTH {
        return Err("expression nesting too deep".into());
    }
    if pos >= tokens.len() {
        return Err("unexpected end of expression".into());
    }
    match &tokens[pos] {
        Token::Num(n) => Ok((Expr::Literal(*n), pos + 1)),
        Token::LParen => {
            let (expr, p) = parse_ternary(tokens, pos + 1)?;
            if p >= tokens.len() || tokens[p] != Token::RParen {
                return Err("missing closing parenthesis".into());
            }
            Ok((expr, p + 1))
        }
        Token::Ident(name) => {
            let aliases = aliases();
            let resolved = aliases.get(name.as_str()).map(|s| s.to_string()).unwrap_or_else(|| name.clone());

            // Check for function call
            if pos + 1 < tokens.len() && tokens[pos + 1] == Token::LParen {
                let args_start = pos + 2;
                let (args, end_pos) = parse_args(tokens, args_start, depth + 1)?;
                let (expr, _) = build_func(&resolved, args)?;
                return Ok((expr, end_pos));
            }
            // adv{N} pattern
            if resolved.starts_with("adv") {
                if let Ok(n) = resolved[3..].parse::<usize>() {
                    return Ok((Expr::TsMean(Box::new(Expr::Column("volume".into())), n), pos + 1));
                }
            }
            Ok((Expr::Column(resolved), pos + 1))
        }
        _ => Err(format!("unexpected token: {:?}", tokens[pos])),
    }
}

fn parse_args(tokens: &[Token], mut pos: usize, _depth: usize) -> Result<(Vec<Expr>, usize), String> {
    let mut args = Vec::new();
    if pos < tokens.len() && tokens[pos] == Token::RParen {
        return Ok((args, pos + 1));
    }
    loop {
        let (arg, p) = parse_ternary(tokens, pos)?;
        args.push(arg);
        pos = p;
        if pos >= tokens.len() {
            return Err("missing closing parenthesis in function call".into());
        }
        if tokens[pos] == Token::RParen {
            return Ok((args, pos + 1));
        }
        if tokens[pos] != Token::Comma {
            return Err(format!("expected ',' or ')' in function args, got {:?}", tokens[pos]));
        }
        pos += 1;
    }
}

fn expect_window(args: &[Expr], idx: usize, name: &str) -> Result<usize, String> {
    match &args[idx] {
        Expr::Literal(n) => {
            let w = *n as usize;
            if w == 0 || w > MAX_WINDOW {
                return Err(format!("{name}: window must be 1..{MAX_WINDOW}, got {w}"));
            }
            Ok(w)
        }
        _ => Err(format!("{name}: window must be a literal integer")),
    }
}

fn build_func(name: &str, args: Vec<Expr>) -> Result<(Expr, usize), String> {
    // We return (Expr, end_pos) but end_pos is already handled by caller.
    // Wrap in Ok with dummy pos 0 — caller ignores it.
    let expr = match name {
        // Unary element-wise
        "log" => { check_args(name, &args, 1)?; Expr::Log(b(&args, 0)) }
        "abs" => { check_args(name, &args, 1)?; Expr::Abs(b(&args, 0)) }
        "sign" => { check_args(name, &args, 1)?; Expr::Sign(b(&args, 0)) }
        "scale" => { check_args(name, &args, 1)?; Expr::Scale(b(&args, 0)) }
        "tanh" => { check_args(name, &args, 1)?; Expr::Tanh(b(&args, 0)) }
        "sigmoid" => { check_args(name, &args, 1)?; Expr::Sigmoid(b(&args, 0)) }
        "exp" => { check_args(name, &args, 1)?; Expr::Exp(b(&args, 0)) }
        "sqrt" => { check_args(name, &args, 1)?; Expr::Sqrt(b(&args, 0)) }

        // Cross-sectional
        "rank" => { check_args(name, &args, 1)?; Expr::Rank(b(&args, 0)) }
        "zscore" => { check_args(name, &args, 1)?; Expr::Zscore(b(&args, 0)) }

        // Time-series (col, window)
        "ts_mean" => { check_args(name, &args, 2)?; let w = expect_window(&args, 1, name)?; Expr::TsMean(b(&args, 0), w) }
        "ts_std" => { check_args(name, &args, 2)?; let w = expect_window(&args, 1, name)?; Expr::TsStd(b(&args, 0), w) }
        "ts_max" => { check_args(name, &args, 2)?; let w = expect_window(&args, 1, name)?; Expr::TsMax(b(&args, 0), w) }
        "ts_min" => { check_args(name, &args, 2)?; let w = expect_window(&args, 1, name)?; Expr::TsMin(b(&args, 0), w) }
        "ts_sum" => { check_args(name, &args, 2)?; let w = expect_window(&args, 1, name)?; Expr::TsSum(b(&args, 0), w) }
        "ts_shift" => { check_args(name, &args, 2)?; let w = expect_window(&args, 1, name)?; Expr::TsShift(b(&args, 0), w) }
        "ts_delta" => { check_args(name, &args, 2)?; let w = expect_window(&args, 1, name)?; Expr::TsDelta(b(&args, 0), w) }
        "ts_rank" => { check_args(name, &args, 2)?; let w = expect_window(&args, 1, name)?; Expr::TsRank(b(&args, 0), w) }
        "ts_argmax" => { check_args(name, &args, 2)?; let w = expect_window(&args, 1, name)?; Expr::TsArgmax(b(&args, 0), w) }
        "ts_argmin" => { check_args(name, &args, 2)?; let w = expect_window(&args, 1, name)?; Expr::TsArgmin(b(&args, 0), w) }
        "decay_linear" => { check_args(name, &args, 2)?; let w = expect_window(&args, 1, name)?; Expr::DecayLinear(b(&args, 0), w) }
        "product" => { check_args(name, &args, 2)?; let w = expect_window(&args, 1, name)?; Expr::Product(b(&args, 0), w) }
        "ts_av_diff" => { check_args(name, &args, 2)?; let w = expect_window(&args, 1, name)?; Expr::TsAvDiff(b(&args, 0), w) }
        "ts_zscore" => { check_args(name, &args, 2)?; let w = expect_window(&args, 1, name)?; Expr::TsZscore(b(&args, 0), w) }
        "ema" => { check_args(name, &args, 2)?; let w = expect_window(&args, 1, name)?; Expr::Ema(b(&args, 0), w) }
        "rsi" => { check_args(name, &args, 2)?; let w = expect_window(&args, 1, name)?; Expr::Rsi(b(&args, 0), w) }
        "macd" => { check_args(name, &args, 2)?; let w = expect_window(&args, 1, name)?; Expr::Macd(b(&args, 0), w) }
        "obv" => { check_args(name, &args, 2)?; let w = expect_window(&args, 1, name)?; Expr::TsSum(b(&args, 0), w) }
        "boll_upper" => { check_args(name, &args, 2)?; let w = expect_window(&args, 1, name)?; Expr::BollUpper(b(&args, 0), w) }
        "boll_lower" => { check_args(name, &args, 2)?; let w = expect_window(&args, 1, name)?; Expr::BollLower(b(&args, 0), w) }
        "boll_mid" => { check_args(name, &args, 2)?; let w = expect_window(&args, 1, name)?; Expr::BollMid(b(&args, 0), w) }

        // Dual time-series
        "ts_corr" => { check_args(name, &args, 3)?; let w = expect_window(&args, 2, name)?; Expr::TsCorr(b(&args, 0), b(&args, 1), w) }
        "ts_cov" => { check_args(name, &args, 3)?; let w = expect_window(&args, 2, name)?; Expr::TsCov(b(&args, 0), b(&args, 1), w) }

        // Binary
        "power" => { check_args(name, &args, 2)?; Expr::Power(b(&args, 0), b(&args, 1)) }
        "sign_power" => { check_args(name, &args, 2)?; Expr::SignPower(b(&args, 0), b(&args, 1)) }
        "max" => { check_args(name, &args, 2)?; Expr::Max(b(&args, 0), b(&args, 1)) }
        "min" => { check_args(name, &args, 2)?; Expr::Min(b(&args, 0), b(&args, 1)) }

        // Ternary
        "where" => { check_args(name, &args, 3)?; Expr::Where(b(&args, 0), b(&args, 1), b(&args, 2)) }
        "clip" => { check_args(name, &args, 3)?; Expr::Clip(b(&args, 0), b(&args, 1), b(&args, 2)) }

        _ => return Err(format!("unknown operator: {name}")),
    };
    Ok((expr, 0))
}

fn check_args(name: &str, args: &[Expr], expected: usize) -> Result<(), String> {
    if args.len() != expected {
        return Err(format!("{name} expects {expected} args, got {}", args.len()));
    }
    Ok(())
}

fn b(args: &[Expr], idx: usize) -> Box<Expr> {
    Box::new(args[idx].clone())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_simple_column() {
        let expr = parse("close").unwrap();
        assert!(matches!(expr, Expr::Column(ref s) if s == "close"));
    }

    #[test]
    fn test_arithmetic() {
        let expr = parse("close / open").unwrap();
        assert!(matches!(expr, Expr::Div(_, _)));
    }

    #[test]
    fn test_rank() {
        let expr = parse("rank(close / vwap)").unwrap();
        assert!(matches!(expr, Expr::Rank(_)));
    }

    #[test]
    fn test_ts_mean() {
        let expr = parse("ts_mean(close, 20)").unwrap();
        assert!(matches!(expr, Expr::TsMean(_, 20)));
    }

    #[test]
    fn test_nested() {
        let expr = parse("rank(ts_delta(close / vwap, 5))").unwrap();
        assert!(matches!(expr, Expr::Rank(_)));
    }

    #[test]
    fn test_alias() {
        let expr = parse("delay(close, 1)").unwrap();
        assert!(matches!(expr, Expr::TsShift(_, 1)));
    }

    #[test]
    fn test_adv() {
        let expr = parse("adv20").unwrap();
        assert!(matches!(expr, Expr::TsMean(_, 20)));
    }

    #[test]
    fn test_ternary_python() {
        let expr = parse("close if close > open else open").unwrap();
        assert!(matches!(expr, Expr::Where(_, _, _)));
    }
}
