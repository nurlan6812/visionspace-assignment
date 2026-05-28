"use client";

import { useEffect, useMemo, useState, useTransition } from "react";
import { AlertTriangle, FileJson, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import type { SceneCase, SceneEntity, SceneSpec } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TrackShell } from "@/components/track-shell";

const fallbackCases: SceneCase[] = [
  {
    id: "case-agv-grid",
    input: "AGV 6대를 700평 직사각형 공장에 격자 배치하고, 출입구 근처 2대는 회피 우선 모드로 설정해줘",
  },
  {
    id: "case-conveyor-rack",
    input: "1200제곱미터 창고에 컨베이어 3개를 중앙 라인으로 배치하고 양쪽에 랙 12개를 놓아줘",
  },
  {
    id: "case-robot-arm",
    input: "로봇팔 4대를 조립 셀 주변에 배치하고 작업자 2명은 안전 구역 밖에 위치시켜줘",
  },
  {
    id: "case-mixed",
    input:
      "AMR 8 units, conveyor 2 units, and 1 charging station in a rectangular 900 m2 warehouse. Prioritize collision avoidance near the entrance.",
  },
  {
    id: "case-ambiguous",
    input: "작은 물류센터에 AGV 여러 대와 랙을 적당히 배치해줘. 속도는 낮게 설정해줘",
  },
];

function formatPlacement(entity: SceneEntity) {
  const parts: string[] = [];
  if (entity.placement.pattern && entity.placement.pattern !== "unspecified") {
    parts.push(entity.placement.pattern);
  }
  if (entity.placement.zone && entity.placement.zone !== "unspecified") {
    parts.push(entity.placement.zone);
  }
  if (entity.placement.near) {
    parts.push(`near ${entity.placement.near}`);
  }
  return parts.length ? parts.join(" · ") : "미지정";
}

function PropertyList({ entity }: Readonly<{ entity: SceneEntity }>) {
  const entries = Object.entries(entity.properties ?? {});
  if (!entries.length) {
    return <span className="text-slate-400">추가 설정 없음</span>;
  }

  return (
    <div className="space-y-1">
      {entries.map(([key, value]) => (
        <div key={key} className="rounded-sm bg-vision-panel px-2 py-1">
          <span className="text-[11px] font-bold text-vision-muted">{key}</span>
          <span className="ml-2 text-[11px] text-slate-700">
            {typeof value === "string" || typeof value === "number" || typeof value === "boolean"
              ? String(value)
              : JSON.stringify(value)}
          </span>
        </div>
      ))}
    </div>
  );
}

function EntityTable({ entities }: Readonly<{ entities: SceneEntity[] }>) {
  if (entities.length === 0) {
    return <p className="text-sm text-slate-500">아직 파싱된 entity가 없습니다.</p>;
  }

  return (
    <div className="overflow-hidden border border-vision-line">
      <table className="w-full border-collapse text-left text-sm">
        <thead className="bg-vision-panel text-xs uppercase tracking-[0.14em] text-vision-muted">
          <tr>
            <th className="px-3 py-2">Entity</th>
            <th className="px-3 py-2">수량</th>
            <th className="px-3 py-2">배치</th>
            <th className="px-3 py-2">세부 설정</th>
          </tr>
        </thead>
        <tbody>
          {entities.map((entity, index) => (
            <tr key={`${entity.type}-${entity.quantity}-${index}`} className="border-t border-vision-line">
              <td className="px-3 py-3 font-bold text-vision-navy">{entity.type}</td>
              <td className="px-3 py-3 font-mono">{entity.quantity}</td>
              <td className="px-3 py-3 text-slate-700">{formatPlacement(entity)}</td>
              <td className="px-3 py-3 font-mono text-xs text-slate-600">
                <PropertyList entity={entity} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SummaryTile({
  label,
  value,
  hint,
}: Readonly<{ label: string; value: string; hint?: string }>) {
  return (
    <div className="border border-vision-line bg-vision-panel/70 p-4">
      <div className="text-[11px] font-bold uppercase tracking-[0.16em] text-vision-muted">{label}</div>
      <div className="mt-2 text-lg font-bold text-vision-navy">{value}</div>
      {hint ? <p className="mt-2 text-xs leading-5 text-slate-500">{hint}</p> : null}
    </div>
  );
}

export function Track3SceneMini() {
  const [cases, setCases] = useState<SceneCase[]>(fallbackCases);
  const [selectedCaseId, setSelectedCaseId] = useState(fallbackCases[0].id);
  const [sceneText, setSceneText] = useState(fallbackCases[0].input);
  const [sceneSpec, setSceneSpec] = useState<SceneSpec | null>(null);
  const [strategy, setStrategy] = useState("hybrid_fallback");
  const [error, setError] = useState<string | null>(null);
  const [isParsing, setIsParsing] = useState(false);
  const [isPending, startTransition] = useTransition();

  const selectedCase = useMemo(() => cases.find((item) => item.id === selectedCaseId), [cases, selectedCaseId]);

  async function loadCases() {
    const nextCases = await api.sceneCases();
    setCases(nextCases);
    if (!nextCases.some((item) => item.id === selectedCaseId) && nextCases[0]) {
      setSelectedCaseId(nextCases[0].id);
      setSceneText(nextCases[0].input);
    }
  }

  useEffect(() => {
    loadCases().catch(() => undefined);
  }, []);

  useEffect(() => {
    if (selectedCase) {
      setSceneText(selectedCase.input);
      setSceneSpec(null);
      setError(null);
    }
  }, [selectedCase]);

  async function submitSceneParse(nextText = sceneText, nextStrategy = strategy) {
    setError(null);
    setIsParsing(true);
    try {
      setSceneSpec(await api.parseScene(nextText, nextStrategy));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setIsParsing(false);
    }
  }


  return (
    <TrackShell
      badge="Track 3 · Scene 해석"
      title="자연어 Scene Parser"
      description="자연어 지시를 SceneSpec으로 정리하고, 핵심 메타 정보와 파싱된 entity만 보여주는 Track 3 데모입니다."
    >
      {error ? (
        <div className="mb-6 border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertTriangle className="mr-2 inline h-4 w-4" />
          {error}
        </div>
      ) : null}

      <div className="mb-6 flex flex-wrap gap-2">
        <Badge tone="navy">Function · parse_scene_to_scene_spec</Badge>
        <Badge tone={sceneSpec?.tool_call.fallback_used ? "warn" : sceneSpec ? "ok" : "neutral"}>
          실행기 · {sceneSpec?.tool_call.executor ?? "-"}
        </Badge>
        <Badge tone={sceneSpec ? "ok" : "neutral"}>Provider · {sceneSpec?.tool_call.provider ?? "-"}</Badge>
      </div>

      <div className="grid gap-8 xl:grid-cols-[360px_minmax(0,1fr)_460px]">
        <Card stripe="navy" className="flex flex-col">
          <CardHeader>
            <CardTitle>입력</CardTitle>
            <p className="mt-2 text-xs leading-5 text-slate-500">
              예시 문장을 고르거나 직접 입력한 뒤 파싱을 실행합니다.
            </p>
          </CardHeader>
          <CardContent className="flex flex-1 flex-col space-y-4">
            <label className="block">
              <span className="text-xs font-bold uppercase tracking-[0.16em] text-vision-muted">예시 케이스</span>
              <select
                value={selectedCaseId}
                onChange={(event) => setSelectedCaseId(event.target.value)}
                className="mt-2 w-full border border-vision-line bg-white px-3 py-2 text-sm"
              >
                {cases.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.id}
                  </option>
                ))}
              </select>
            </label>

            <label className="block">
              <span className="text-xs font-bold uppercase tracking-[0.16em] text-vision-muted">전략</span>
              <select
                value={strategy}
                onChange={(event) => setStrategy(event.target.value)}
                className="mt-2 w-full border border-vision-line bg-white px-3 py-2 text-sm"
              >
                <option value="hybrid_fallback">hybrid_fallback · OpenAI 우선, 실패 시 rule fallback</option>
                <option value="llm_structured_output">llm_structured_output · OpenAI만 사용</option>
                <option value="deterministic_tool">deterministic_tool · rule parser만 사용</option>
              </select>
            </label>

            <textarea
              value={sceneText}
              onChange={(event) => setSceneText(event.target.value)}
              className="min-h-[200px] w-full flex-1 resize-none border border-vision-line bg-white px-3 py-3 text-sm leading-6"
            />

            <div className="flex flex-wrap gap-2">
              <Button variant="primary" onClick={() => void submitSceneParse()} disabled={isParsing}>
                <FileJson className="mr-2 h-4 w-4" /> {isParsing ? "파싱 중..." : "파싱 실행"}
              </Button>
              <Button variant="secondary" onClick={() => startTransition(() => void loadCases())} disabled={isPending}>
                <RefreshCw className="mr-2 h-4 w-4" /> 예시 새로고침
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card stripe="none" className="flex flex-col overflow-hidden">
          <CardHeader>
            <CardTitle>Raw JSON</CardTitle>
            <p className="mt-2 text-xs leading-5 text-slate-500">
              parser가 반환한 SceneSpec 전체 구조입니다. 길어져도 이 영역 안에서만 스크롤됩니다.
            </p>
          </CardHeader>
          <CardContent className="flex flex-1 flex-col p-0">
            <pre className="min-h-[480px] flex-1 overflow-y-auto overflow-x-hidden whitespace-pre-wrap break-all bg-[#101318] p-5 font-mono text-xs leading-5 text-slate-100">
              {sceneSpec ? JSON.stringify(sceneSpec, null, 2) : "SceneSpec JSON이 여기에 표시됩니다."}
            </pre>
          </CardContent>
        </Card>

        <Card stripe="amber">
          <CardHeader>
            <CardTitle>씬 요약</CardTitle>
            <p className="mt-2 text-xs leading-5 text-slate-500">
              이 영역은 scene 전체 메타 정보를 요약해서 보여줍니다. 아래 entity 표는 실제 추출 결과만 따로 보여줍니다.
            </p>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="grid gap-3 sm:grid-cols-2">
              <SummaryTile
                label="공간"
                value={sceneSpec ? sceneSpec.space.type : "-"}
                hint={sceneSpec ? "공간 분류" : "파싱 전"}
              />
              <SummaryTile
                label="형태 / 면적"
                value={sceneSpec ? sceneSpec.space.shape : "-"}
                hint={sceneSpec?.space.area_m2 ? `${sceneSpec.space.area_m2} m2` : "면적 정보 없음"}
              />
              <SummaryTile
                label="실행"
                value={sceneSpec?.tool_call.provider ?? sceneSpec?.tool_call.executor ?? "-"}
                hint={sceneSpec?.tool_call.model ?? "파서 실행 전"}
              />
              <SummaryTile
                label="Fallback"
                value={sceneSpec?.tool_call.fallback_used ? "사용됨" : "없음"}
                hint={sceneSpec ? sceneSpec.tool_call.executor ?? "-" : "파싱 전"}
              />
            </div>

            <div className="border-t border-vision-line pt-6">
              <div className="mb-3">
                <h3 className="text-lg font-bold text-vision-navy">파싱된 Entity</h3>
                <p className="mt-1 text-xs leading-5 text-slate-500">
                  자연어에서 실제로 추출된 asset/entity 목록입니다. `세부 설정`은 mode, priority_quantity, speed_profile 같은 동작 옵션이나 추가 파라미터를 뜻합니다.
                </p>
              </div>
              <EntityTable entities={sceneSpec?.entities ?? []} />
            </div>
          </CardContent>
        </Card>
      </div>
    </TrackShell>
  );
}
