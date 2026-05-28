"use client";

import { useEffect, useMemo, useState, useTransition } from "react";
import { AlertTriangle, Boxes, Cpu, Gauge, Layers3, Play, RefreshCw, Upload } from "lucide-react";
import { api, assetUrl } from "@/lib/api";
import type { AssetRecord, AssetType, EnvironmentInfo, GenerationJob, ModelName, ModelStatus, PromptSpec } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { MetricGrid } from "@/components/metric-grid";
import { ModelPreview } from "@/components/model-preview";
import { TrackShell } from "@/components/track-shell";

const SAMPLE_REFERENCE_IMAGES = [
  {
    id: "robot",
    label: "샘플 AGV/robot 이미지",
    path: "/generated/uploads/triposr-robot.png",
    filename: "sample-industrial-robot.png",
  },
  {
    id: "agv-sketch",
    label: "AGV 참조 이미지",
    path: "/generated/uploads/reference-agv.png",
    filename: "reference-agv.png",
  },
  {
    id: "robot-arm-sketch",
    label: "로봇팔 참조 이미지",
    path: "/generated/uploads/reference-robot-arm.png",
    filename: "reference-robot-arm.png",
  },
  {
    id: "conveyor-sketch",
    label: "컨베이어 참조 이미지",
    path: "/generated/uploads/reference-conveyor.png",
    filename: "reference-conveyor.png",
  },
  {
    id: "rack-sketch",
    label: "랙 참조 이미지",
    path: "/generated/uploads/reference-rack.png",
    filename: "reference-rack.png",
  },
  {
    id: "safety-fence-sketch",
    label: "안전펜스 참조 이미지",
    path: "/generated/uploads/reference-safety-fence.png",
    filename: "reference-safety-fence.png",
  },
];


type SampleReferenceImage = (typeof SAMPLE_REFERENCE_IMAGES)[number];

const SAMPLE_REFERENCE_BY_ASSET_TYPE: Partial<Record<AssetType, SampleReferenceImage>> = {
  agv: SAMPLE_REFERENCE_IMAGES[1],
  robot_arm: SAMPLE_REFERENCE_IMAGES[2],
  conveyor: SAMPLE_REFERENCE_IMAGES[3],
  rack: SAMPLE_REFERENCE_IMAGES[4],
  safety_fence: SAMPLE_REFERENCE_IMAGES[5],
};

function sampleForAssetType(assetType: AssetType): SampleReferenceImage | null {
  return SAMPLE_REFERENCE_BY_ASSET_TYPE[assetType] ?? null;
}

function statusTone(status?: string) {
  if (status === "completed") return "ok" as const;
  if (status === "failed") return "error" as const;
  if (status === "running" || status === "queued" || status === "postprocessing") return "warn" as const;
  return "neutral" as const;
}

function formatJobStatus(status?: string) {
  if (!status) return "idle";
  if (status === "queued") return "대기 중";
  if (status === "running") return "생성 중";
  if (status === "postprocessing") return "후처리 중";
  if (status === "completed") return "완료";
  if (status === "failed") return "실패";
  return status;
}

export function Track1AssetFoundry() {
  const [prompts, setPrompts] = useState<PromptSpec[]>([]);
  const [models, setModels] = useState<ModelStatus[]>([]);
  const [environment, setEnvironment] = useState<EnvironmentInfo | null>(null);
  const [jobs, setJobs] = useState<GenerationJob[]>([]);
  const [selectedPromptId, setSelectedPromptId] = useState<string>("");
  const [promptText, setPromptText] = useState("");
  const [selectedModel, setSelectedModel] = useState<ModelName>("triposr");
  const [image, setImage] = useState<File | null>(null);
  const [selectedAsset, setSelectedAsset] = useState<AssetRecord | null>(null);
  const [referencePreviewSrc, setReferencePreviewSrc] = useState<string | null>(null);
  const [referencePreviewLabel, setReferencePreviewLabel] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  const supportedPrompts = useMemo(
    () => prompts.filter((prompt) => sampleForAssetType(prompt.asset_type)),
    [prompts],
  );
  const selectedPrompt = useMemo(
    () => supportedPrompts.find((prompt) => prompt.id === selectedPromptId) ?? supportedPrompts[0] ?? null,
    [supportedPrompts, selectedPromptId],
  );
  const selectedModelStatus = models.find((model) => model.name === selectedModel);
  const latestJob = jobs[0];
  const previewAsset = selectedAsset ?? latestJob?.asset ?? null;
  const previewSrc = assetUrl(previewAsset?.download_url);
  const readyModelCount = models.filter((model) => model.ready).length;
  const runningJob = jobs.find((job) => job.status === "running" || job.status === "postprocessing") ?? null;
  const queuedCount = jobs.filter((job) => job.status === "queued").length;
  const activeJob = runningJob ?? (queuedCount > 0 ? jobs.find((job) => job.status === "queued") ?? null : null);
  const activeJobModel = activeJob ? models.find((model) => model.name === activeJob.request.model)?.label ?? activeJob.request.model : null;
  const hasActiveJob = Boolean(activeJob);
  const canGenerate = Boolean(image && selectedModelStatus?.ready && !hasActiveJob);

  useEffect(() => {
    return () => {
      setReferencePreviewSrc((current) => {
        if (current?.startsWith("blob:")) {
          URL.revokeObjectURL(current);
        }
        return current;
      });
    };
  }, []);

  async function refresh() {
    const [nextPrompts, nextModels, nextEnv, nextJobs] = await Promise.all([
      api.prompts(),
      api.models(),
      api.environment(),
      api.jobs(),
    ]);
    setPrompts(nextPrompts);
    setModels(nextModels);
    setEnvironment(nextEnv);
    setJobs(nextJobs);
    const nextSupportedPrompts = nextPrompts.filter((prompt) => sampleForAssetType(prompt.asset_type));
    if ((!selectedPromptId || !nextSupportedPrompts.some((prompt) => prompt.id === selectedPromptId)) && nextSupportedPrompts[0]) {
      setSelectedPromptId(nextSupportedPrompts[0].id);
      setPromptText(nextSupportedPrompts[0].prompt);
    }
  }

  useEffect(() => {
    refresh().catch((exc) => setError(String(exc)));
    const timer = setInterval(() => {
      api.jobs().then(setJobs).catch(() => undefined);
    }, 3000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (selectedPrompt) {
      setPromptText(selectedPrompt.prompt);
    }
  }, [selectedPrompt]);

  useEffect(() => {
    if (!selectedPrompt) return;
    const sample = sampleForAssetType(selectedPrompt.asset_type);
    if (sample) {
      void useSampleImage(sample.path, sample.filename, sample.label);
    }
  }, [selectedPromptId]);

  function updateReferencePreview(nextSrc: string | null, nextLabel: string) {
    setReferencePreviewSrc((current) => {
      if (current?.startsWith("blob:")) {
        URL.revokeObjectURL(current);
      }
      return nextSrc;
    });
    setReferencePreviewLabel(nextLabel);
  }

  async function useSampleImage(samplePath: string, filename: string, label: string) {
    setError(null);
    try {
      const response = await fetch(assetUrl(samplePath), { cache: "no-store" });
      if (!response.ok) {
        throw new Error(`샘플 이미지를 불러오지 못했습니다. (${response.status})`);
      }
      const blob = await response.blob();
      setImage(new File([blob], filename, { type: blob.type || "image/png" }));
      updateReferencePreview(assetUrl(samplePath), label);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  }

  async function submitGeneration() {
    setError(null);
    if (!image) {
      setError("TripoSR와 Hunyuan3D-2mini는 image-to-3D 모델이라 reference image가 필요합니다.");
      return;
    }
    if (hasActiveJob) {
      setError("현재 생성 job이 진행 중입니다. 완료 후 다음 생성을 실행해 주세요.");
      return;
    }
    try {
      const job = await api.generate({
        prompt: promptText,
        promptId: selectedPromptId,
        model: selectedModel,
        assetType: selectedPrompt?.asset_type ?? "unknown",
        image,
        targetDimensions: selectedPrompt?.target_dimensions_m,
      });
      setJobs((current) => [job, ...current]);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  }

  return (
    <TrackShell
      badge="Track 1 · Text/Image to 3D"
      title="산업 자산 GLB 생성기"
      description="AMR, robot arm, conveyor, rack 등 산업 자산 reference image를 GLB로 생성하고 후처리와 metrics를 확인하는 Track 1 전용 화면입니다."
    >
      <div className="mb-5 grid grid-cols-2 gap-3 text-xs md:grid-cols-5">
        <Badge tone={readyModelCount > 0 ? "ok" : "warn"}>
          모델 {readyModelCount}/{models.length || 2}
        </Badge>
        <Badge tone={environment?.gpu_name ? "ok" : "warn"}>{environment?.gpu_name ?? "GPU unknown"}</Badge>
        <Badge tone="neutral">{environment?.machine ?? "arch"}</Badge>
        <Badge tone="neutral">이미지 필수</Badge>
        <Button variant="secondary" onClick={() => startTransition(() => void refresh())} disabled={isPending}>
          <RefreshCw className="mr-2 h-4 w-4" /> 새로고침
        </Button>
      </div>

      {error && (
        <div className="mb-5 border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertTriangle className="mr-2 inline h-4 w-4" />
          {error}
        </div>
      )}

      <div className="grid gap-8 xl:grid-cols-[420px_1fr_360px]">
        <Card stripe="navy">
          <CardHeader>
            <CardTitle>GLB Asset 생성</CardTitle>
            <p className="mt-2 text-xs text-slate-500">Prompt metadata, 모델 선택, reference image를 입력합니다.</p>
          </CardHeader>
          <CardContent className="space-y-5">
            <label className="block">
              <span className="text-xs font-bold uppercase tracking-[0.16em] text-vision-muted">Prompt preset</span>
              <select
                value={selectedPromptId}
                onChange={(event) => setSelectedPromptId(event.target.value)}
                className="mt-2 w-full border border-vision-line bg-white px-3 py-2 text-sm"
              >
                {supportedPrompts.map((prompt) => (
                  <option key={prompt.id} value={prompt.id}>
                    {prompt.asset_type} · {prompt.title}
                  </option>
                ))}
              </select>
              <p className="mt-2 text-xs text-slate-500">
                프리셋을 선택하면 해당 자산 타입에 맞는 샘플 reference image가 자동으로 연결됩니다.
              </p>
            </label>

            <label className="block">
              <span className="text-xs font-bold uppercase tracking-[0.16em] text-vision-muted">산업 자산 prompt</span>
              <textarea
                value={promptText}
                onChange={(event) => setPromptText(event.target.value)}
                rows={4}
                className="mt-2 w-full resize-none border border-vision-line bg-white px-3 py-3 text-sm leading-6"
              />
            </label>

            <div className="grid grid-cols-2 gap-3">
              {models.map((model) => (
                <button
                  key={model.name}
                  onClick={() => setSelectedModel(model.name)}
                  className={`border p-3 text-left text-sm ${
                    selectedModel === model.name
                      ? "border-vision-navy bg-vision-navy text-white"
                      : "border-vision-line bg-white text-vision-charcoal"
                  }`}
                >
                  <div className="font-bold">{model.label}</div>
                  <div className="mt-2 text-[11px] opacity-80">{model.ready ? "ready" : "setup 필요"}</div>
                </button>
              ))}
            </div>

            {selectedModel === "hunyuan3d_2mini" && (
              <div className="border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                <strong>Hunyuan3D-2mini 안내</strong>
                <p className="mt-1 text-xs leading-5">
                  이 모델은 현재 환경에서 1회 생성에 보통 45~60초 정도 걸립니다. 백엔드는 한 번에 1개 job만 처리하므로,
                  여러 번 누르면 queued 상태로 쌓이고 생성이 안 되는 것처럼 보일 수 있습니다.
                </p>
              </div>
            )}

            {hasActiveJob && (
              <div className="border border-vision-line bg-vision-panel px-4 py-3 text-sm text-vision-charcoal">
                <div className="font-bold">현재 생성 진행 중</div>
                <p className="mt-1 text-xs leading-5 text-slate-600">
                  {activeJobModel} · {formatJobStatus(activeJob?.status)}
                  {queuedCount > 0 ? ` · 대기 ${queuedCount}건` : ""}
                </p>
              </div>
            )}

            <label className="block border border-dashed border-vision-line bg-vision-panel px-4 py-4">
              <span className="flex items-center text-sm font-bold text-vision-navy">
                <Upload className="mr-2 h-4 w-4" /> Reference image(참조 이미지)
              </span>
              <input
                type="file"
                accept="image/*"
                onChange={(event) => {
                  const nextImage = event.target.files?.[0] ?? null;
                  setImage(nextImage);
                  if (nextImage) {
                    updateReferencePreview(URL.createObjectURL(nextImage), nextImage.name);
                  } else {
                    updateReferencePreview(null, "");
                  }
                }}
                className="mt-3 block w-full text-xs"
              />
              {image && <p className="mt-2 text-xs font-mono text-vision-navy">선택된 파일: {image.name}</p>}
              <p className="mt-2 text-xs text-slate-500">
                현재 baseline 모델은 image-to-3D입니다. 텍스트는 asset 설명/평가 metadata로 보존합니다.
              </p>
              <div className="mt-4 border-t border-vision-line pt-3">
                <div className="text-[11px] font-bold uppercase tracking-[0.16em] text-vision-muted">빠른 테스트용 샘플</div>
                <div className="mt-2 grid grid-cols-2 gap-1.5">
                  {SAMPLE_REFERENCE_IMAGES.map((sample) => (
                    <Button
                      key={sample.id}
                      type="button"
                      variant="secondary"
                      className="text-xs"
                      onClick={() => void useSampleImage(sample.path, sample.filename, sample.label)}
                    >
                      {sample.label}
                    </Button>
                  ))}
                </div>
              </div>

              {referencePreviewSrc && (
                <div className="mt-3 border border-vision-line bg-white p-2">
                  <img
                    src={referencePreviewSrc}
                    alt={referencePreviewLabel || "Reference preview"}
                    className="h-28 w-full border border-vision-line bg-white object-contain"
                  />
                  <p className="mt-1.5 text-[11px] font-mono text-vision-navy">{referencePreviewLabel}</p>
                </div>
              )}
            </label>

            <Button className="w-full" variant="amber" onClick={submitGeneration} disabled={!canGenerate}>
              <Play className="mr-2 h-4 w-4" /> {hasActiveJob ? "현재 job 완료 후 생성 가능" : "생성 시작"}
            </Button>
          </CardContent>
        </Card>

        <Card stripe="none" className="overflow-hidden bg-[#101318] xl:sticky xl:top-6 xl:self-start">
          <div className="flex items-center justify-between border-b border-white/10 px-6 py-4 text-white">
            <div>
              <div className="font-mono text-xs uppercase tracking-[0.18em] text-vision-amber">GLB Preview</div>
              <div className="mt-1 text-lg font-bold">{previewAsset?.prompt_id ?? previewAsset?.id ?? "선택된 asset 없음"}</div>
            </div>
            <Badge tone={statusTone(latestJob?.status)}>{formatJobStatus(latestJob?.status)}</Badge>
          </div>
          <ModelPreview src={previewSrc} />
        </Card>

        <div className="space-y-5 xl:sticky xl:top-6 xl:self-start">
          <Card stripe="amber">
            <CardHeader>
              <CardTitle>Asset Metrics</CardTitle>
            </CardHeader>
            <CardContent>
              <MetricGrid metrics={previewAsset?.normalized_metrics ?? previewAsset?.metrics} />
            </CardContent>
          </Card>

          <Card stripe="navy">
            <CardHeader>
              <CardTitle>실행 환경</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="flex items-center justify-between"><span>플랫폼</span><span className="font-mono">{environment?.machine ?? "-"}</span></div>
              <div className="flex items-center justify-between"><span>CUDA</span><span className="font-mono">{environment?.cuda_version ?? "-"}</span></div>
              <div className="flex items-center justify-between"><span>GPU</span><span className="font-mono">{environment?.gpu_name ?? "-"}</span></div>
              <div className="flex items-center justify-between"><span>디스크</span><span className="font-mono">{environment?.disk_available ?? "-"}</span></div>
            </CardContent>
          </Card>
        </div>
      </div>

      <Card stripe="amber" className="mt-8">
        <CardHeader>
          <CardTitle>생성 Job</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="mb-5 grid gap-3 md:grid-cols-2">
            {models.map((model) => (
              <div key={model.name} className="border border-vision-line bg-vision-panel p-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-vision-navy">{model.label}</span>
                  <Badge tone={model.ready ? "ok" : "warn"}>{model.ready ? "ready" : "setup 필요"}</Badge>
                </div>
                <p className="mt-2 line-clamp-2 text-xs text-slate-500">{model.reason}</p>
              </div>
            ))}
          </div>

          <div className="space-y-3">
            {jobs.length === 0 && <p className="text-sm text-slate-500">아직 생성 job이 없습니다.</p>}
            {jobs.map((job) => (
              <button
                key={job.id}
                onClick={() => job.asset && setSelectedAsset(job.asset)}
                className="w-full border border-vision-line bg-white p-3 text-left"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-sm font-bold text-vision-navy">{job.id}</span>
                  <Badge tone={statusTone(job.status)}>{formatJobStatus(job.status)}</Badge>
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-4 text-xs text-slate-500">
                  <span className="flex items-center"><Cpu className="mr-1 h-3 w-3" /> {models.find((model) => model.name === job.request.model)?.label ?? job.request.model}</span>
                  <span className="flex items-center"><Boxes className="mr-1 h-3 w-3" /> {job.asset?.asset_type ?? job.request.asset_type ?? "-"}</span>
                  <span className="flex items-center"><Gauge className="mr-1 h-3 w-3" /> {job.asset?.normalized_metrics?.faces ?? job.asset?.metrics?.faces ?? "-"} faces</span>
                  <span className="flex items-center"><Layers3 className="mr-1 h-3 w-3" /> GLB</span>
                </div>
                {job.error && <p className="mt-2 text-xs text-red-600">{job.error}</p>}
              </button>
            ))}
          </div>
        </CardContent>
      </Card>
    </TrackShell>
  );
}
