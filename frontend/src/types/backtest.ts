export type TaskStatus =
  | "pending"
  | "generating_expression"
  | "validating"
  | "fetching_data"
  | "backtesting"
  | "generating_report"
  | "completed"
  | "failed";

export interface BacktestRequest {
  prompt: string;
  universe?: string;
  start_date?: string;
  end_date?: string;
  n_groups?: number;
  holding_period?: number;
  benchmark?: string;
}

export interface BacktestMetrics {
  total_return: number;
  cagr: number;
  sharpe: number;
  sortino: number;
  max_drawdown: number;
  volatility: number;
  win_rate: number;
  profit_factor: number;
}

export interface GroupReturn {
  group: string;
  annual_return: number;
  sharpe: number;
  max_drawdown: number;
}

export interface BacktestResult {
  report_url: string;
  metrics: BacktestMetrics;
  backtest_summary: {
    long_short_sharpe: number;
    monotonicity_score: number;
    spread: number;
    group_returns: Record<string, GroupReturn>;
  };
  params: {
    expression: string;
    universe: string;
    start_date: string;
    end_date: string;
    n_groups: number;
    holding_period: number;
    benchmark: string;
    stock_count: number;
  };
  llm: {
    prompt: string;
    generated_expression: string;
  };
}

export interface Task {
  task_id: string;
  status: TaskStatus;
  params?: BacktestRequest;
  expression?: string;
  error?: string;
  result?: BacktestResult;
}
