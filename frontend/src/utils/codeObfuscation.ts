export function getStrategyCode(result: {
  strategy_code?: string;
}): string | null {
  return result.strategy_code ?? null;
}
