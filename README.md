# TESSERACT Asset Foundry

VisionSpace AI Developer 사전과제 구현입니다.

선택 트랙은 `Track 1 Text/Image to 3D`이고, 필수 트랙은 `Track 3 Text-to-Scene Mini`입니다. 프론트엔드는 두 트랙을 독립 페이지로 분리했습니다.

전체 Text-to-Simulation 아키텍처는 [`ARCHITECTURE.md`](ARCHITECTURE.md)에 정리했습니다.

## 목표

산업 자동화 시뮬레이션에 필요한 scene을 자연어에서 구조화하고, 필요한 자산을 생성해 simulator-ready workflow로 연결합니다.

```text
User natural language
  -> Track 3: SceneSpec / SceneGraph
  -> downstream task handoff
  -> Track 1: GLB asset generation
  -> postprocess / metrics / preview
```

이 저장소는 "Track 1 데모"와 "Track 3 데모"를 따로 보여주되, 내부 설계는 하나의 Text-to-Simulation pipeline으로 맞췄습니다.

## 현재 환경 기준

이 저장소는 현재 로컬 환경을 기준으로 구성했습니다.

- OS/arch: Ubuntu `aarch64`
- GPU: NVIDIA GB10, CUDA 13.0
- Python: 3.12
- Node: 22
- npm: 10

GB10/aarch64 환경은 일반 x86_64 CUDA PyTorch wheel과 다를 수 있으므로, 모델 repo, 모델별 Python 환경, checkpoint cache를 분리했습니다. 기본 백엔드와 UI는 먼저 설치하고, heavy model dependency는 `models/envs` 아래에 별도로 준비합니다.

## 빠른 실행

```bash
uv venv
uv pip install -e '.[dev]'
npm --prefix frontend install
```

백엔드:

```bash
source .venv/bin/activate
vsaf serve --host 127.0.0.1 --port 8000
```

프론트엔드:

```bash
npm --prefix frontend run dev
```

브라우저에서 아래 URL을 엽니다.

- `http://localhost:3000/track1`: Track 1 Text/Image to 3D
- `http://localhost:3000/track3`: Track 3 Text-to-Scene Mini

Track 1은 image-to-3D 모델을 사용하므로 reference image가 필요합니다. 데모 편의를 위해 아래 샘플 이미지를 함께 제공합니다.

- `outputs/uploads/triposr-robot.png`
- `outputs/uploads/reference-agv.png`
- `outputs/uploads/reference-robot-arm.png`
- `outputs/uploads/reference-conveyor.png`
- `outputs/uploads/reference-rack.png`
- `outputs/uploads/reference-safety-fence.png`

Track 3의 LLM 경로는 기본적으로 로컬 vLLM 서버(Qwen3.6)에 OpenAI 호환 API로 붙도록 잡혀 있습니다. base URL이 비어 있으면 OpenAI 경로로 폴백합니다.

vLLM 사용 (기본):

```bash
export OPENAI_API_KEY=EMPTY
export VSAF_SCENE_PARSER_OPENAI_BASE_URL=http://localhost:8003/v1
export VSAF_SCENE_PARSER_OPENAI_MODEL=local-main
```

OpenAI 사용 (옵션):

```bash
unset VSAF_SCENE_PARSER_OPENAI_BASE_URL
export OPENAI_API_KEY=sk-...
export VSAF_SCENE_PARSER_OPENAI_MODEL=gpt-4o-mini
```

## 모델 repo 준비

```bash
source .venv/bin/activate
python scripts/setup_model_repos.py --clone
```

이후 각 모델 환경에 PyTorch와 공식 repo dependency를 설치합니다. 현재 머신은 `aarch64 + NVIDIA GB10 + CUDA 13.0`이므로, 스크립트는 uv-managed Python `3.12.13`, PyTorch `2.12.0+cu130`, torchvision `0.27.0+cu130`을 기본으로 사용하고 모델별 venv를 만듭니다.

```bash
python scripts/setup_model_envs.py --model all
export TRIPOSR_PYTHON=/home/jaekwang/visionspace/models/envs/triposr/bin/python
export HUNYUAN3D_PYTHON=/home/jaekwang/visionspace/models/envs/hunyuan3d/bin/python
export HF_HOME=/home/jaekwang/visionspace/models/cache/huggingface
```

checkpoint를 먼저 받아두려면:

```bash
models/envs/hunyuan3d/bin/python scripts/download_model_weights.py --model all
```

설치 검증:

```bash
vsaf models
```

실제 smoke test:

```bash
vsaf generate triposr models/repos/TripoSR/examples/robot.png \
  "Industrial mobile robot reference asset for simulation-ready GLB validation" \
  --asset-type agv --prompt-id smoke-triposr-robot

HUNYUAN3D_STEPS=5 HUNYUAN3D_OCTREE_RESOLUTION=128 HUNYUAN3D_NUM_CHUNKS=8000 \
vsaf generate hunyuan3d_2mini models/repos/TripoSR/examples/robot.png \
  "Hunyuan3D mini smoke test for industrial robot GLB pipeline" \
  --asset-type agv --prompt-id smoke-hunyuan-robot
```

긴 모델 실행은 `VSAF_MODEL_TIMEOUT_SECONDS`로 제한할 수 있습니다.

### TripoSR

공식 실행 방식:

```bash
cd models/repos/TripoSR
python run.py examples/chair.png --output-dir output/
```

이 프로젝트의 runner는 `TRIPOSR_REPO`와 `TRIPOSR_PYTHON` 환경 변수를 읽어 같은 명령을 호출합니다.

### Hunyuan3D-2mini

이 프로젝트의 runner는 공식 repo의 `hy3dgen`을 import하고 다음 모델 설정을 사용합니다.

```bash
HUNYUAN3D_MODEL_PATH=tencent/Hunyuan3D-2mini
HUNYUAN3D_SUBFOLDER=hunyuan3d-dit-v2-mini
```

## 과제용 reference image 생성

산업 자산 샘플 이미지가 더 필요하면 아래 스크립트로 정면 reference image를 다시 만들 수 있습니다.

```bash
python3 scripts/generate_reference_images.py
```

## CLI

```bash
vsaf env
vsaf models
vsaf prompts
vsaf scene "AGV 6대를 700평 직사각형 공장에 격자 배치하고, 출입구 근처 2대는 회피 우선 모드로 설정해줘"
vsaf scene-tool-schema
vsaf validate-scenes
vsaf inspect outputs/assets/example.glb
vsaf normalize input.glb output-normalized.glb --target-largest-dimension-m 2.0
```

모델 repo 준비 후 이미지 기반 생성:

```bash
vsaf generate triposr reference.png "A low-profile AMR for warehouse logistics" --asset-type agv
```

## API

- `GET /api/environment`: 로컬 실행 환경 진단
- `GET /api/models`: 모델 repo 준비 상태
- `GET /api/prompts`: 산업 자산 프롬프트 세트
- `POST /api/generate`: 이미지 업로드와 함께 생성 job 생성
- `GET /api/jobs`: 생성 job 목록
- `GET /api/assets`: 생성 asset 목록
- `GET /api/scene/cases`: Track 3 자체 검증 케이스 5개
- `GET /api/scene/tool-schema`: Agent/function-calling용 scene parsing tool contract
- `POST /api/scene/parse`: 자연어를 `SceneSpec` + `SceneGraphSpec` + downstream handoff plan으로 변환
  입력 contract는 `user_instruction`이며, 하위 호환을 위해 기존 `text` payload도 허용
- `/generated/assets/*.glb`: 생성 GLB static serving

## Track 3 Architecture

Track 3는 JSON 변환기 역할을 넘어서, agentic Text-to-Simulation workflow에서 호출 가능한 scene interpretation tool로 설계했습니다.

```text
User instruction
  -> parse_scene_to_scene_spec tool contract
  -> Pydantic SceneSpec validation
  -> SceneGraphSpec nodes/edges
  -> downstream task handoff
  -> asset resolution / layout generation / simulator export / validation
```

현재 runtime은 세 가지 전략을 지원합니다.

- `deterministic_tool`: alias + regex rule parser만 사용
- `llm_structured_output`: OpenAI structured output으로 scene draft를 만든 뒤 `SceneSpec`으로 정규화
- `hybrid_fallback`: OpenAI 경로를 먼저 시도하고 실패 시 deterministic parser로 fallback

## 검증

```bash
source .venv/bin/activate
pytest -q
npm --prefix frontend run build
```

## UI

UI는 과제 문서의 디자인 가이드를 따릅니다.

- Navy: `#0F2D5C`
- Amber: `#D97706`
- Card-based layout
- 왼쪽 color stripe
- status badge
- GLB preview 중심
- metrics/report 노출

기술 스택:

- Next.js App Router
- Tailwind CSS
- shadcn/ui 스타일의 로컬 컴포넌트
- `<model-viewer>` GLB preview

페이지 구성:

- `/`: Track 1 / Track 3 분리 랜딩
- `/track1`: 이미지 기반 GLB 생성, job 상태, metrics, GLB preview
- `/track3`: 입력, Raw JSON, 씬 요약, 파싱된 Entity 중심의 scene interpretation 화면

## 제출 문서

- `REPORT.md`: 모델 비교, 후처리, 실패 분석
- `RETROSPECTIVE.md`: 의사결정 근거와 회고
- `ARCHITECTURE.md`: Text-to-Simulation 전체 구조

## GLB 샘플

`outputs/samples/`에 평가용 GLB 5개와 매칭되는 metrics JSON을 함께 둡니다. `outputs/` 전체는 `.gitignore` 대상이지만 `outputs/samples/`만 예외로 commit합니다.

- `agv-triposr.glb` / `metrics/agv-triposr.json` — REPORT §4.1 표의 AGV TripoSR 케이스
- `agv-hunyuan3d-2mini.glb` / `metrics/agv-hunyuan3d-2mini.json` — AGV Hunyuan3D-2mini 케이스
- `robot_arm-triposr.glb` / `metrics/robot_arm-triposr.json` — Robot arm TripoSR (articulated 구조 붕괴 사례)
- `conveyor-triposr.glb` — Conveyor TripoSR (반복 roller 구조 손실 사례)
- `rack-triposr.glb` — Rack TripoSR (반복 bay 구조 손실 사례)

## 리스크

- 모델 자체는 image-to-3D 중심이므로 텍스트 입력은 asset prompt metadata로 보관하고 reference image를 함께 사용합니다.
- GB10/aarch64 환경의 PyTorch/CUDA 호환성은 모델 설치 전 확인이 필요합니다.
- Blender CLI가 현재 환경에 없어서 기본 후처리는 `trimesh` 기반 scale normalization으로 구현했습니다.
