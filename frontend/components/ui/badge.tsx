import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

export function Badge({
  children,
  tone = "neutral",
}: Readonly<{ children: ReactNode; tone?: "neutral" | "ok" | "warn" | "error" | "navy" }>) {
  return (
    <span
      className={cn(
        "inline-flex items-center border px-2 py-1 text-[11px] font-bold tracking-[0.06em]",
        tone === "neutral" && "border-slate-300 bg-slate-50 text-slate-600",
        tone === "ok" && "border-emerald-300 bg-emerald-50 text-emerald-700",
        tone === "warn" && "border-amber-300 bg-amber-50 text-amber-700",
        tone === "error" && "border-red-300 bg-red-50 text-red-700",
        tone === "navy" && "border-vision-navy bg-vision-navy text-white",
      )}
    >
      {children}
    </span>
  );
}
