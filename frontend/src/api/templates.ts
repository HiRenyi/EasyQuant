import { authFetch, parseError, BASE } from "./client";

export interface FactorTemplate {
  id: string;
  name: string;
  category: string;
  description: string;
  expression: string;
  tags: string[];
  difficulty: "beginner" | "intermediate" | "advanced";
  suggested_params: {
    universe: string;
    holding_period: number;
    n_groups: number;
  };
  reference: string;
}

export async function fetchTemplates(category?: string): Promise<FactorTemplate[]> {
  const params = new URLSearchParams();
  if (category) params.set("category", category);
  const qs = params.toString();
  const url = `${BASE}/api/v1/templates${qs ? `?${qs}` : ""}`;
  const res = await authFetch(url);
  if (!res.ok) throw new Error(await parseError(res));
  const data = await res.json();
  return data.templates;
}
