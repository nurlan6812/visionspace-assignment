import type { MeshMetrics } from "@/lib/types";

function formatBytes(value?: number | null) {
  if (!value) return "-";
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KiB`;
  return `${(value / 1024 / 1024).toFixed(1)} MiB`;
}

export function MetricGrid({ metrics }: Readonly<{ metrics?: MeshMetrics | null }>) {
  const items = [
    ["Faces", metrics?.faces?.toLocaleString() ?? "-"],
    ["Vertices", metrics?.vertices?.toLocaleString() ?? "-"],
    ["Mesh 수", metrics?.mesh_count?.toString() ?? "-"],
    ["파일 크기", formatBytes(metrics?.file_size_bytes)],
    ["최대 길이", metrics?.largest_dimension_m ? `${metrics.largest_dimension_m.toFixed(2)} m` : "-"],
    ["Watertight", metrics?.is_watertight == null ? "-" : metrics.is_watertight ? "yes" : "no"],
  ];
  return (
    <div className="grid grid-cols-2 gap-3">
      {items.map(([label, value]) => (
        <div key={label} className="border border-vision-line bg-vision-panel p-3">
          <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-vision-muted">{label}</div>
          <div className="mt-1 font-mono text-lg font-bold text-vision-navy">{value}</div>
        </div>
      ))}
    </div>
  );
}
