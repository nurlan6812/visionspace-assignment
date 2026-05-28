"use client";

import { Box } from "lucide-react";
import { createElement, useEffect, useState } from "react";

export function ModelPreview({ src }: Readonly<{ src?: string }>) {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    import("@google/model-viewer").then(() => setReady(true));
  }, []);

  if (!src) {
    return (
      <div className="flex min-h-[460px] items-center justify-center bg-[#101318] text-slate-400">
        <div className="text-center">
          <Box className="mx-auto mb-4 h-12 w-12 text-vision-amber" />
          <p className="font-mono text-sm">선택된 GLB가 없습니다</p>
          <p className="mt-2 text-xs">Asset을 생성하거나 기존 job을 선택하면 여기에서 preview됩니다.</p>
        </div>
      </div>
    );
  }

  if (!ready) {
    return (
      <div className="flex min-h-[460px] items-center justify-center bg-[#101318] font-mono text-sm text-slate-400">
        GLB viewer 로딩 중...
      </div>
    );
  }

  return createElement("model-viewer", {
    src,
    alt: "Generated industrial asset",
    "camera-controls": true,
    "auto-rotate": true,
    exposure: "0.9",
    "shadow-intensity": "0.75",
    "environment-image": "neutral",
  });
}
