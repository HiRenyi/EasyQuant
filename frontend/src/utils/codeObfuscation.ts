const OBF_KEY = "qgpt2026xk9";

export function decryptCode(encrypted: string): string {
  const keyBytes = new TextEncoder().encode(OBF_KEY);
  const raw = Uint8Array.from(atob(encrypted), (c) => c.charCodeAt(0));
  const decoded = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) {
    decoded[i] = raw[i] ^ keyBytes[i % keyBytes.length];
  }
  return new TextDecoder().decode(decoded);
}

export function getStrategyCode(result: {
  strategy_code?: string;
  strategy_code_encrypted?: string;
}): string | null {
  if (result.strategy_code) return result.strategy_code;
  if (result.strategy_code_encrypted) {
    try {
      return decryptCode(result.strategy_code_encrypted);
    } catch {
      return null;
    }
  }
  return null;
}
