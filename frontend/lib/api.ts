import type { EnvironmentInfo, GenerationJob, ModelName, ModelStatus, PromptSpec, SceneCase, SceneSpec, SceneToolSchema } from "./types";

const CONFIGURED_API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL;

function apiBase() {
  if (CONFIGURED_API_BASE) return CONFIGURED_API_BASE;
  if (typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname}:8001`;
  }
  return "http://127.0.0.1:8001";
}

export function assetUrl(path?: string | null) {
  if (!path) return "";
  if (path.startsWith("http")) return path;
  return `${apiBase()}${path}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase()}${path}`, {
    ...init,
    cache: "no-store",
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  environment: () => request<EnvironmentInfo>("/api/environment"),
  models: () => request<ModelStatus[]>("/api/models"),
  prompts: () => request<PromptSpec[]>("/api/prompts"),
  jobs: () => request<GenerationJob[]>("/api/jobs"),
  job: (id: string) => request<GenerationJob>(`/api/jobs/${id}`),
  sceneCases: () => request<SceneCase[]>("/api/scene/cases"),
  sceneToolSchema: () => request<SceneToolSchema>("/api/scene/tool-schema"),
  parseScene: (userInstruction: string, strategy = "deterministic_tool") =>
    request<SceneSpec>("/api/scene/parse", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_instruction: userInstruction, strategy }),
    }),
  generate: (payload: {
    prompt: string;
    promptId?: string;
    model: ModelName;
    assetType: string;
    image?: File | null;
    targetDimensions?: unknown;
  }) => {
    const form = new FormData();
    form.set("prompt", payload.prompt);
    form.set("model", payload.model);
    form.set("asset_type", payload.assetType);
    if (payload.promptId) form.set("prompt_id", payload.promptId);
    if (payload.targetDimensions) form.set("target_dimensions_m", JSON.stringify(payload.targetDimensions));
    if (payload.image) form.set("image", payload.image);
    return request<GenerationJob>("/api/generate", {
      method: "POST",
      body: form,
    });
  },
};
