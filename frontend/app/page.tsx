import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function Home() {
  return (
    <main className="mx-auto max-w-[1280px] px-6 py-10">
      <header className="mb-8 border-b border-vision-line pb-7">
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <Badge tone="navy">VISION SPACE · AI Developer</Badge>
          <Badge tone="warn">트랙별 분리 데모</Badge>
        </div>
        <h1 className="text-4xl font-black tracking-tight text-vision-navy">TESSERACT 사전과제 데모</h1>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-600">
          Track 1과 Track 3를 독립 화면으로 분리했습니다. 제출 시에도 선택 트랙과 필수 트랙의 요구사항,
          검증 결과, 리포트를 분리해서 설명할 수 있는 구조입니다.
        </p>
      </header>

      <div className="grid gap-8 lg:grid-cols-2">
        <Card stripe="navy">
          <CardHeader>
            <div className="mb-2"><Badge tone="neutral">선택 트랙</Badge></div>
            <CardTitle>Track 1 · Text/Image to 3D</CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            <p className="text-sm leading-6 text-slate-600">
              산업 자산 reference image를 TripoSR 또는 Hunyuan3D-2mini로 GLB 생성하고, scale normalization과
              mesh metrics를 확인하는 화면입니다.
            </p>
            <div className="grid gap-2 text-sm">
              <div className="border border-vision-line bg-vision-panel px-3 py-2">산업 자산 prompt set 10개 이상</div>
              <div className="border border-vision-line bg-vision-panel px-3 py-2">TripoSR / Hunyuan3D-2mini 비교 대상</div>
              <div className="border border-vision-line bg-vision-panel px-3 py-2">GLB preview + 후처리 metrics</div>
            </div>
            <Link href="/track1">
              <Button variant="amber">Track 1 열기</Button>
            </Link>
          </CardContent>
        </Card>

        <Card stripe="amber">
          <CardHeader>
            <div className="mb-2"><Badge tone="warn">필수 트랙</Badge></div>
            <CardTitle>Track 3 · Text-to-Scene Mini</CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            <p className="text-sm leading-6 text-slate-600">
              자연어 명령을 Pydantic schema로 검증되는 JSON scene spec으로 변환합니다. 5개 케이스, edge/default
              handling, Scene Graph 확장성을 독립적으로 보여줍니다.
            </p>
            <div className="grid gap-2 text-sm">
              <div className="border border-vision-line bg-vision-panel px-3 py-2">6종 entity type 지원</div>
              <div className="border border-vision-line bg-vision-panel px-3 py-2">공간, 수량, 배치, 속성 파싱</div>
              <div className="border border-vision-line bg-vision-panel px-3 py-2">Edge case는 assumptions / warnings로 기록</div>
            </div>
            <Link href="/track3">
              <Button variant="primary">Track 3 열기</Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
