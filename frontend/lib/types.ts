export type AssetType =
  | "agv"
  | "robot_arm"
  | "conveyor"
  | "rack"
  | "pallet_box"
  | "worker"
  | "charging_station"
  | "safety_fence"
  | "unknown";

export type ModelName = "triposr" | "hunyuan3d_2mini";

export interface PromptSpec {
  id: string;
  asset_type: AssetType;
  title: string;
  prompt: string;
  target_dimensions_m?: { x: number; y: number; z: number } | null;
  notes?: string | null;
}

export interface ModelStatus {
  name: ModelName;
  label: string;
  ready: boolean;
  reason: string;
  requires_image: boolean;
  repo: string;
}

export interface EnvironmentInfo {
  platform: string;
  machine: string;
  python_version: string;
  cuda_version?: string | null;
  gpu_name?: string | null;
  gpu_memory_total?: string | null;
  system_memory_total?: string | null;
  disk_available?: string | null;
  node_version?: string | null;
  npm_version?: string | null;
  blender_available: boolean;
  ffmpeg_available: boolean;
  torch_available: boolean;
  torch_version?: string | null;
  torch_cuda_available: boolean;
  torch_cuda_version?: string | null;
  recommendations: string[];
}

export interface MeshMetrics {
  file_size_bytes: number;
  vertices?: number | null;
  faces?: number | null;
  mesh_count?: number | null;
  largest_dimension_m?: number | null;
  is_watertight?: boolean | null;
  has_materials?: boolean | null;
  has_textures?: boolean | null;
  warnings: string[];
}

export interface AssetRecord {
  id: string;
  prompt_id?: string | null;
  title?: string | null;
  asset_type: AssetType;
  model: ModelName;
  prompt: string;
  source_image?: string | null;
  raw_path?: string | null;
  glb_path: string;
  normalized_path?: string | null;
  download_url?: string | null;
  metrics?: MeshMetrics | null;
  normalized_metrics?: MeshMetrics | null;
  created_at: string;
  notes: string[];
}

export interface GenerationRequestSummary {
  prompt_id?: string | null;
  prompt: string;
  asset_type: AssetType;
  model: ModelName;
  image_path?: string | null;
  target_dimensions_m?: { x: number; y: number; z: number } | null;
  bake_texture: boolean;
  texture_resolution: number;
}

export interface GenerationJob {
  id: string;
  status: "queued" | "running" | "postprocessing" | "completed" | "failed";
  request: GenerationRequestSummary;
  asset?: AssetRecord | null;
  error?: string | null;
  logs: string[];
}

export interface SceneCase {
  id: string;
  input: string;
}

export interface SpaceSpec {
  type: "factory" | "warehouse" | "workspace";
  shape: "rectangle" | "unknown";
  area_m2?: number | null;
  area_source?: string | null;
  units: "m";
}

export interface PlacementSpec {
  pattern: string;
  zone?: string | null;
  near?: string | null;
  notes: string[];
}

export interface SceneEntity {
  type: AssetType;
  quantity: number;
  placement: PlacementSpec;
  properties: Record<string, unknown>;
}

export interface SceneGraphNode {
  id: string;
  kind: "space" | "entity_group" | "zone" | "constraint" | "task";
  label: string;
  ref_type?: string | null;
  attributes: Record<string, unknown>;
}

export interface SceneGraphEdge {
  source: string;
  target: string;
  relation: string;
  attributes: Record<string, unknown>;
}

export interface SceneGraphSpec {
  nodes: SceneGraphNode[];
  edges: SceneGraphEdge[];
}

export interface ToolCallSpec {
  name: string;
  version: string;
  strategy: "deterministic_tool" | "llm_structured_output" | "hybrid_fallback";
  input_schema_ref: string;
  output_schema_ref: string;
  validation: "pending" | "passed" | "failed";
  provider?: string | null;
  model?: string | null;
  executor?: string | null;
  fallback_used: boolean;
  notes: string[];
}

export interface DownstreamTaskSpec {
  name: "asset_resolution" | "layout_generation" | "simulation_export" | "scene_validation";
  status: "ready" | "needs_confirmation" | "blocked";
  consumes: string[];
  produces: string[];
  notes: string[];
}

export interface SceneSpec {
  version: string;
  source_text: string;
  space: SpaceSpec;
  entities: SceneEntity[];
  global_constraints: Record<string, unknown>;
  required_asset_types: AssetType[];
  scene_graph: SceneGraphSpec;
  downstream_tasks: DownstreamTaskSpec[];
  tool_call: ToolCallSpec;
  assumptions: string[];
  warnings: string[];
}

export interface SceneToolSchema {
  tool: Record<string, unknown>;
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
}
