// Types for strategy backtest (JoinQuant automation)

export type StrategyTaskStatus =
  | "pending"
  | "generating_code"
  | "validating_code"
  | "logging_in"
  | "launching_browser"
  | "setting_code"
  | "configuring_backtest"
  | "running_backtest"
  | "waiting_completion"
  | "scraping_results"
  | "completed"
  | "failed"
  | "cancelled";

export interface StrategyBacktestRequest {
  prompt: string;
  start_date?: string;
  end_date?: string;
  initial_capital?: number;
  benchmark?: string;
  session_id?: string;
}

export interface StrategyMetrics {
  total_return?: number;
  annual_return?: number;
  excess_return?: number;
  sharpe_ratio?: number;
  sortino_ratio?: number;
  information_ratio?: number;
  max_drawdown?: number;
  alpha?: number;
  beta?: number;
  volatility?: number;
  benchmark_return?: number;
  benchmark_volatility?: number;
  win_rate?: number;
  daily_win_rate?: number;
  profit_loss_ratio?: number;
  [key: string]: number | undefined;
}

export interface EquityCurvePoint {
  date: string;
  strategy_return: number;
  benchmark_return: number;
  excess_return?: number;
  daily_profit?: number;
  daily_loss?: number;
  daily_buy?: number;
  daily_sell?: number;
}

export interface StrategyTrade {
  [key: string]: string | number | undefined;
}

export interface DailyPosition {
  [key: string]: string | number | undefined;
}

export interface StrategyBacktestResult {
  metrics: StrategyMetrics;
  equity_curve: EquityCurvePoint[];
  trades: StrategyTrade[];
  daily_positions: DailyPosition[];
  strategy_code?: string;
  strategy_code_encrypted?: string;
  csv_path?: string;
  params: {
    prompt: string;
    start_date: string;
    end_date: string;
    initial_capital: number;
    benchmark: string;
  };
}

export interface StrategyTask {
  task_id: string;
  status: StrategyTaskStatus;
  task_type?: "strategy_backtest";
  session_id?: string;
  strategy_code?: string;
  strategy_code_encrypted?: string;
  validation?: {
    valid: boolean;
    errors: string[];
    warnings: string[];
  };
  error?: string;
  result?: StrategyBacktestResult;
  params?: StrategyBacktestRequest;
}
