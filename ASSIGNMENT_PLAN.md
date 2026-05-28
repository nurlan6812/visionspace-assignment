# VisionSpace AI Developer 사전과제 계획

작성일: 2026-05-21

## 1. 결론

진행 방향은 `Track 1 Text/Image to 3D` 선택 + `Track 3 Text-to-Scene Mini` 필수 구현으로 고정한다.

이번 과제의 1차 목표는 +A 확장이 아니라, 과제 문서의 기본 요구사항을 재현 가능하게 충족하는 것이다. 모델 튜닝, 고급 랭킹, Figma 연동, Storybook 등은 기본 제출물이 안정화된 뒤 추가한다.

핵심 메시지는 다음과 같이 잡는다.

> 산업 자산을 텍스트/이미지에서 GLB로 생성하고, 후처리와 품질 확인을 거쳐 TESSERACT 시뮬레이션에 투입 가능한 형태로 정리하는 파이프라인을 구현했다.

## 2. 과제 문서 재확인

### Track 1 요구사항

| 항목 | 요구사항 | 구현 계획 |
| --- | --- | --- |
| 도메인 프롬프트 | AMR, 로봇팔, 컨베이어, 랙, 창고 박스 등 산업 자산 프롬프트 10개 이상 | `data/prompts/industrial_assets.jsonl`에 카테고리별 프롬프트 정리 |
| 모델 비교 | TripoSR, Hunyuan3D-2 mini 등 8GB 이하 모델 2개 선정 | `TripoSR`를 baseline, `Hunyuan3D-2mini`를 quality candidate로 비교 |
| 후처리 | Mesh decimation, 스케일 정규화, 텍스처 베이킹 중 1개 이상 자동화 | 1순위 `scale normalization`, 2순위 `mesh decimation` |
| 데모 | Gradio/Streamlit 데모 또는 자유 UI | 최종은 `Next.js + Tailwind + shadcn/ui + model-viewer` |
| 실패 분석 | 프롬프트 5개 이상 실패 케이스 분석 | 산업 자산별 실패 원인: 형태 붕괴, 비대칭, wheel/arm 누락, texture artifact, scale 불일치 |
| 제출물 | GitHub repo, 비교 실험 결과표, GLB 샘플 5개, 2분 데모 영상 | `README.md`, `REPORT.md`, `RETROSPECTIVE.md`, `outputs/assets/*.glb` |

### Track 3 요구사항

| 항목 | 요구사항 | 구현 계획 |
| --- | --- | --- |
| 입력 | 자연어 명령 | Korean/English mixed prompt 지원 |
| 출력 | 구조화 JSON scene spec | Pydantic schema 기반 JSON |
| entity | 최소 3개 타입 | `agv`, `robot_arm`, `conveyor`, `rack`, `worker` |
| 파싱 | 공간, 수량, 속성 파라미터 | 면적, 배치 방식, 모드, 우선순위, 속도 등 |
| 검증 | 5개 입력 케이스 자체 검증 | `tests/test_scene_parser.py` 또는 CLI 검증 스크립트 |

### UI 디자인 요구사항

과제 문서의 데모 UI 기준은 다음이다.

| 구분 | 요구사항 |
| --- | --- |
| 컬러 | Primary Navy `#0F2D5C`, Accent Amber `#D97706`, Background White `#FFFFFF`, Text Charcoal `#1A1A1A` |
| 타이포그래피 | Sans-serif, 명확한 위계, Header 24~36pt, Body 13~14pt, Caption 10~11pt, Mono는 Consolas |
| 레이아웃 | Card-based, 충분한 여백, 왼쪽 4~8px color stripe, border-radius 최소 사용, 2~3 컬럼 |
| 컴포넌트 | 단순 버튼, 명확한 라벨, status badge, navy/amber 데이터 시각화, 장식 최소화 |

## 3. 회사 및 도메인 컨텍스트 반영

기업소개서 기준으로 TESSERACT의 핵심은 다음이다.

| 컨텍스트 | UI/구현 반영 |
| --- | --- |
| Web-Based Physical AI Simulation | 웹에서 바로 GLB preview와 생성 상태 확인 |
| Text-to-Simulation | Track 3 scene spec과 Track 1 asset generation을 연결 |
| Digital Twin | asset metadata에 scale, category, bounding box, unit 정보를 포함 |
| Operational Twin | 생성 결과를 단순 이미지가 아니라 시뮬레이션 자산 후보로 표현 |
| Synthetic Data | 실패 케이스와 품질 지표를 데이터로 남기는 구조 |
| 현장 중심 실행력 | 프롬프트를 AMR, 컨베이어, 랙, 팔레트 등 물류/제조 자산 중심으로 제한 |

## 4. 모델 전략

### 기본 모델

| 모델 | 역할 | 선택 이유 | 리스크 |
| --- | --- | --- | --- |
| TripoSR | 빠른 baseline | 공식 repo가 안정적이고 single image to 3D 재현성이 좋음 | texture 품질과 산업 자산 디테일이 약할 수 있음 |
| Hunyuan3D-2mini | 품질 비교군 | 과제 추천 모델이고 Hunyuan3D 계열은 shape/texture 파이프라인이 명확함 | 설치 의존성과 texture 단계 VRAM 이슈 가능 |

### 보류 모델

| 모델/API | 보류 이유 | 사용 시점 |
| --- | --- | --- |
| Stable Fast 3D | UV unwrap, textured mesh가 강점이지만 접근 동의와 라이선스 확인 필요 | 기본 결과가 나온 뒤 비교 후보 |
| TRELLIS.2 | 고품질 PBR asset 후보이나 4B급으로 기본 범위를 넘길 수 있음 | 서버 GPU 여유와 시간이 있을 때 +A |
| Meshy API | text-to-3D API가 편하지만 외부 유료 API 의존성이 커짐 | 로컬 모델 실패 시 fallback 또는 참고 비교 |

## 5. UI 및 디자인 도구 조사

### 최종 UI 스택 결정

| 도구 | 용도 | 결정 |
| --- | --- | --- |
| Next.js App Router | 데모 웹앱 프레임워크 | 사용 |
| Tailwind CSS | 디자인 토큰과 레이아웃 | 사용 |
| shadcn/ui | 카드, 버튼, 탭, 배지, 테이블 | 사용 |
| `<model-viewer>` | GLB preview | 1차 사용 |
| React Three Fiber | 고급 3D scene interaction | 보류 |
| Gradio | 빠른 Python ML 데모 | fallback |
| Streamlit | 데이터 앱 데모 | 이번 과제에는 보류 |

Next.js를 고르는 이유는 UI 품질과 컴포넌트 제어가 Gradio/Streamlit보다 좋기 때문이다. 과제 문서가 Gradio/Streamlit을 허용하지만, 디자인 톤 정렬이 평가 기준에 포함되어 있으므로 최종 데모는 Next.js가 더 적합하다.

### 유용한 MCP 및 프론트 도구

| 도구 | 용도 | 이번 과제 적용 |
| --- | --- | --- |
| Figma MCP | Figma 디자인을 코드/에이전트에 연결 | 현재 첨부는 PDF/PPT라 즉시 사용하지 않음. Figma 파일이 생기면 사용 |
| shadcn MCP | shadcn registry와 컴포넌트 컨텍스트를 AI 에디터에 제공 | Next.js UI 구현 시 유용. 디자인 토큰을 registry로 관리할 경우 사용 |
| Playwright MCP | 브라우저 자동화, 접근성 snapshot, 스크린샷 | UI 완성 후 데모 플로우 검증과 스크린샷 캡처에 사용 후보 |
| Chrome DevTools MCP | live Chrome 디버깅, console/network/performance trace | 최종 데모 전 성능, 콘솔 에러, 렌더링 문제 확인에 사용 후보 |
| Context7 | 최신 라이브러리 문서 조회 | Next.js, shadcn/ui, model-viewer 구현 중 문서 확인용 |
| v0 | React/Tailwind/shadcn UI 초안 생성 | 디자인 시안 참고용. 생성 코드는 반드시 수동 검토 |
| Storybook | 컴포넌트 문서화와 interaction test | 과제 일정상 보류. UI 컴포넌트가 많아지면 추가 |

### MCP 사용 우선순위

| 우선순위 | 도구 | 이유 |
| --- | --- | --- |
| 1 | Playwright MCP | 실제 데모 플로우가 깨지지 않는지 확인하고 스크린샷을 남길 수 있음 |
| 2 | Chrome DevTools MCP | GLB viewer와 Next.js UI의 console/performance 문제를 잡기 좋음 |
| 3 | shadcn MCP | UI 컴포넌트 확장 속도를 높일 수 있음 |
| 4 | Figma MCP | 현재는 Figma 파일이 없으므로 보류 |

### 주의할 점

MCP는 로컬 브라우저, 파일, 디자인 계정에 접근할 수 있으므로 공식 서버 위주로 사용한다. 특히 browser automation 계열 MCP는 필요한 프로젝트에서만 켜고, 계정 로그인 세션이나 API key가 포함된 브라우저 프로필과 분리한다.

## 6. UI 설계안

### 페이지 구조

| 영역 | 내용 |
| --- | --- |
| Header | `TESSERACT Asset Foundry`, 진행 상태 badge, 제출 일정 |
| Left Panel | 입력 프롬프트, asset type, model selector, image upload |
| Center Panel | GLB preview, generation progress, selected asset metadata |
| Right Panel | metrics card: latency, VRAM, faces, file size, postprocess status |
| Bottom Tabs | `Prompt Set`, `Model Comparison`, `Failure Analysis`, `Scene JSON` |

### 화면 톤

| 요소 | 디자인 방향 |
| --- | --- |
| 배경 | 흰색 기반, 얇은 grid 또는 light blueprint 느낌 |
| 카드 | 왼쪽 navy/amber stripe, radius 작게, 여백 크게 |
| 버튼 | primary navy, 실행/강조 amber |
| 상태 표시 | `queued`, `running`, `postprocessed`, `failed`, `validated` badge |
| 3D preview | 어두운 viewport 카드로 기업소개서의 관제 UI 분위기 일부 반영 |
| 데이터 표 | navy text, amber highlight, mono 숫자 |

### 데모 플로우

1. 산업 자산 프롬프트 선택 또는 입력
2. 이미지가 필요한 모델이면 reference image 업로드
3. 모델 선택: TripoSR 또는 Hunyuan3D-2mini
4. 생성 실행
5. GLB preview와 metadata 확인
6. 후처리 실행 또는 자동 후처리 결과 확인
7. 모델 비교표와 실패 분석 확인
8. Track 3 scene JSON에서 필요한 asset type 확인

## 7. 구현 구조

```text
visionspace/
  README.md
  REPORT.md
  RETROSPECTIVE.md
  ASSIGNMENT_PLAN.md
  data/
    prompts/
      industrial_assets.jsonl
    scene_cases/
      text_to_scene_cases.json
  outputs/
    assets/
    renders/
    metrics/
  src/
    asset_pipeline/
      generate.py
      models/
        triposr_runner.py
        hunyuan_runner.py
      postprocess/
        normalize_scale.py
        decimate.py
        inspect_mesh.py
      evaluation/
        compare_models.py
    scene_parser/
      schema.py
      parser.py
      validate_cases.py
  frontend/
    app/
    components/
    lib/
    public/generated-assets/
```

## 8. 일정

### 2026-05-21

| 작업 | 목표 |
| --- | --- |
| 프롬프트 세트 작성 | 산업 자산 10개 이상 |
| Track 3 schema 작성 | Pydantic 기반 scene spec |
| UI skeleton 작성 | Next.js layout, design token, 주요 카드 |
| 모델 환경 확인 | TripoSR 우선 실행 가능 여부 확인 |

### 2026-05-22 중간보고

| 작업 | 목표 |
| --- | --- |
| Track 3 최소 동작 | 5개 케이스 중 일부라도 validation 가능 |
| Track 1 초기 결과 | GLB 샘플 1개 이상 또는 모델 실행 로그 |
| UI 방향 제시 | mock/skeleton screenshot |
| 중간보고 문서 | 선택 이유, 모델 비교 기준, 리스크, 다음 계획 |

### 2026-05-25 ~ 2026-05-27

| 작업 | 목표 |
| --- | --- |
| 모델 2개 비교 | TripoSR, Hunyuan3D-2mini 결과 생성 |
| GLB 샘플 | 5개 이상 정리 |
| 후처리 자동화 | scale normalization 또는 decimation |
| 실패 분석 | 5개 이상 케이스와 원인 정리 |

### 2026-05-28 ~ 2026-05-29

| 작업 | 목표 |
| --- | --- |
| 최종 UI | 데모 플로우 완성 |
| 문서 | README, REPORT, RETROSPECTIVE 작성 |
| 영상 | 2분 이내 데모 녹화 |
| 최종 제출 | GitHub repo 링크 제출 |

## 9. 중간보고에 넣을 내용

| 섹션 | 내용 |
| --- | --- |
| 선택 트랙 | Track 1 선택, Track 3 필수 병행 |
| 선택 이유 | 모델링 관심과 TESSERACT Text-to-Simulation 맥락이 직접 연결됨 |
| 모델 선택 | TripoSR는 빠른 baseline, Hunyuan3D-2mini는 품질 비교군 |
| UI 방향 | 비전스페이스 디자인 가이드 기반 Next.js demo |
| 현재 진행 | 프롬프트 세트, schema, UI skeleton, 모델 환경 확인 |
| 리스크 | 설치 의존성, GLB 품질 편차, scale/postprocess 안정성 |
| 다음 계획 | 모델 비교, 후처리 자동화, 실패 분석, 데모 영상 |

## 10. 리스크와 대응

| 리스크 | 영향 | 대응 |
| --- | --- | --- |
| Hunyuan3D 설치 지연 | 모델 비교 지연 | TripoSR + Stable Fast 3D 또는 InstantMesh fallback |
| 산업 자산 형태 붕괴 | GLB 품질 저하 | reference image 기반 생성, 프롬프트 constraint 강화 |
| 텍스처 품질 부족 | 데모 완성도 저하 | geometry 중심 비교와 texture 한계 명시 |
| scale 불일치 | 시뮬레이션 자산성 약화 | postprocess에서 unit/bounding box metadata 생성 |
| UI 구현 과다 | 모델 실험 시간 감소 | Next.js skeleton은 단순화, 핵심은 GLB preview와 비교표 |
| MCP 보안/설정 문제 | 일정 지연 | MCP는 필수 경로가 아니라 QA 보조 도구로만 사용 |

## 11. 출처

| 항목 | 링크 |
| --- | --- |
| Figma MCP | https://help.figma.com/hc/en-us/articles/32132100833559-Guide-to-the-Figma-MCP-server |
| shadcn MCP | https://ui.shadcn.com/docs/registry/mcp |
| Playwright MCP | https://playwright.dev/docs/getting-started-mcp |
| Chrome DevTools MCP | https://github.com/ChromeDevTools/chrome-devtools-mcp |
| v0 | https://v0.app/docs |
| v0 Design Systems | https://v0.app/docs/design-systems |
| Next.js App Router | https://nextjs.org/docs/app |
| Tailwind theme variables | https://tailwindcss.com/docs/theme |
| shadcn/ui components | https://ui.shadcn.com/docs/components |
| model-viewer | https://modelviewer.dev/ |
| React Three Fiber | https://r3f.docs.pmnd.rs/getting-started/introduction |
| Storybook interaction tests | https://storybook.js.org/docs/9/writing-tests/interaction-testing |
| TripoSR | https://github.com/VAST-AI-Research/TripoSR |
| Hunyuan3D-2 | https://github.com/Tencent-Hunyuan/Hunyuan3D-2 |
| Stable Fast 3D | https://huggingface.co/stabilityai/stable-fast-3d |
| TRELLIS.2 | https://github.com/microsoft/TRELLIS.2 |

