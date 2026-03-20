export type TaskStatus =
  | "pending"
  | "generating_expression"
  | "validating"
  | "fetching_data"
  | "backtesting"
  | "generating_report"
  | "completed"
  | "failed"
  | "iterating"
  | "iteration_completed";

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

export interface IterationCandidate {
  expression: string;
  score: number;
  grade: "A" | "B" | "C" | "D";
  component_scores: Record<string, number>;
  backtest_summary: {
    long_short_sharpe: number;
    monotonicity_score: number;
    spread: number;
    group_returns: Record<string, GroupReturn>;
  };
  report_metrics: BacktestMetrics;
  report_url: string;
  status: "success" | "failed";
  error?: string;
}

export interface BacktestResult {
  report_url: string;
  metrics: BacktestMetrics;
  backtest_summary: {
    long_short_sharpe: number;
    top_group_sharpe?: number;
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

export interface Session {
  id: string;
  name: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface Task {
  task_id: string;
  status: TaskStatus;
  session_id?: string;
  params?: BacktestRequest;
  expression?: string;
  error?: string;
  result?: BacktestResult;
  task_type?: "backtest" | "iteration";
  parent_task_id?: string;
  candidates?: IterationCandidate[];
  candidates_done?: number;
  candidates_total?: number;
  selected_candidate_index?: number;
}
