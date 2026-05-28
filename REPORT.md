# REPORT

## 1. 제출 범위

- 선택 트랙: `Track 1 Text/Image to 3D`
- 필수 트랙: `Track 3 Text-to-Scene Mini`

이번 구현은 Track 1과 Track 3를 따로 만든 것이 아니라, `Text-to-Simulation` 파이프라인 안에서 서로 연결되는 두 모듈로 설계했습니다.

```text
사용자 자연어
  -> Track 3 SceneSpec / SceneGraph
  -> 필요한 asset type 추출
  -> Track 1 GLB asset generation
  -> postprocess / preview / simulator handoff
```

이번 구현에서 가장 신경 쓴 부분은 재현성, tool contract, 그리고 도메인 한계의 명시였습니다.

## 2. 환경과 제약

- OS/arch: `Linux aarch64`
- GPU: `NVIDIA GB10`
- CUDA: `13.0`
- Python: `3.12`
- Frontend: `Next.js 16`
- LLM 서빙: 로컬 vLLM (`Qwen/Qwen3.6-35B-A3B-FP8`, served-model-name=`local-main`, `http://localhost:8003/v1`). OpenAI(`gpt-4o-mini`) 경로도 호환합니다.

실무적으로 가장 큰 제약은 두 가지였습니다.

1. 현재 선택 모델인 `TripoSR`, `Hunyuan3D-2mini`가 모두 `image-to-3D` 계열이라는 점
2. `GB10/aarch64` 환경이 일반적인 `x86_64 CUDA` 환경과 달라 모델별 격리 환경 구성이 필요했다는 점

그래서 모델 runner는 메인 앱 환경과 분리했고, prompt-only text-to-3D를 무리하게 붙이기보다 `reference image 기반 asset generation`을 명시하는 쪽을 선택했습니다.

## 3. Track 1 설계

### 3.1 모델 선택

| 모델 | 역할 | 선택 이유 | 리스크 |
| --- | --- | --- | --- |
| `TripoSR` | 빠른 baseline | 설치/재현이 안정적이고 속도가 빠름 | 얇은 구조, 반복 구조, 관절 구조에서 붕괴 가능성 |
| `Hunyuan3D-2mini` | 품질 비교군 | 과제 문서 추천 모델이며 shape fidelity 기대치가 높음 | latency, mesh density, VRAM/운영 비용 부담 |

### 3.2 후처리

구현한 후처리 파이프라인은 다음과 같습니다.

- mesh/scene을 GLB로 통일
- uniform scale normalization
- floor alignment
- mesh metrics 수집
  - vertices
  - faces
  - file size
  - watertight
  - bounding box

최종 제출 직전 `Scene transform을 metrics가 무시하던 버그`를 수정했습니다. 이 수정으로 normalize 이후 bbox와 floor alignment가 실제 출력 파일에 반영되는지 회귀 테스트까지 추가했습니다.

### 3.3 실험 입력

실험에 사용한 reference image는 두 종류입니다.

- 기존 샘플: `outputs/uploads/triposr-robot.png`
- 과제용으로 추가 생성한 정면 reference image: `scripts/generate_reference_images.py`

추가 생성한 산업 자산 reference image는 다음과 같습니다.

- `reference-agv.png`
- `reference-robot-arm.png`
- `reference-conveyor.png`
- `reference-rack.png`
- `reference-safety-fence.png`

실험 평가는 ground-truth mesh가 없기 때문에 다음 proxy metric 중심으로 잡았습니다.

- end-to-end latency
- faces / vertices / file size
- watertight 여부
- 목표 치수 대비 axis-aligned bounding box 경향
- 반복 구조 / 얇은 구조 / articulated structure 보존 가능성

## 4. Track 1 비교 결과

### 4.1 공통 비교 케이스

아래 표는 두 모델을 같은 카테고리에서 비교한 결과입니다. bbox는 `raw mesh` 기준입니다. uniform normalization은 절대 크기만 조정하므로, 실패 분석의 핵심인 `형상 비율 왜곡`은 raw bbox로 보는 것이 더 적절했습니다.

| asset | 모델 | latency(s) | faces | vertices | file size | bbox(m) | watertight | 관찰 포인트 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AGV | TripoSR | 7.06 | 156,010 | 78,133 | 3.12 MB | 0.713 x 0.970 x 0.987 | False | 빠르고 가볍지만 높이 방향이 과장됨 |
| AGV | Hunyuan3D-2mini | 53.46 | 1,130,256 | 565,094 | 20.35 MB | 1.901 x 1.994 x 1.595 | False | 메시 복잡도는 높지만 simulator asset으로는 너무 무거움 |
| Robot arm | TripoSR | 8.34 | 22,824 | 11,429 | 0.46 MB | 0.102 x 0.569 x 0.952 | False | 한 축이 심하게 납작해져 articulated arm이 평면처럼 붕괴될 위험 |
| Robot arm | Hunyuan3D-2mini | 56.86 | 280,480 | 140,241 | 5.05 MB | 1.343 x 1.994 x 0.913 | False | TripoSR보다 볼륨은 살아 있으나 크기와 방향이 과장됨 |
| Safety fence | TripoSR | 7.36 | 162,407 | 81,330 | 3.25 MB | 0.907 x 0.998 x 0.875 | False | 얇은 panel 구조가 두꺼운 덩어리로 뭉개짐 |
| Safety fence | Hunyuan3D-2mini | 55.97 | 511,336 | 255,454 | 9.20 MB | 1.995 x 1.807 x 0.058 | True | 얇은 sheet 성향은 유지되지만 orientation/scale 해석이 불안정 |

### 4.2 TripoSR 추가 케이스

`TripoSR`은 빠른 baseline으로 두고 반복 구조와 길쭉한 산업 자산에서 어떤 실패가 나는지 보기 위해 추가 케이스를 더 돌렸습니다.

| asset | latency(s) | faces | file size | bbox(m) | 관찰 포인트 |
| --- | --- | --- | --- | --- | --- |
| Conveyor | 7.23 | 52,663 | 1.06 MB | 0.164 x 1.023 x 0.556 | 길이 중심 실루엣은 남지만 폭 방향이 심하게 축소 |
| Rack | 7.59 | 418,707 | 8.38 MB | 0.879 x 0.885 x 0.942 | 랙의 반복 bay 구조가 거의 정육면체 덩어리로 수렴 |

## 5. Track 1 실패 분석

피드백에서 강조된 부분이 "성공 샘플보다 실패 원인 분석"이었기 때문에, 실패를 `하드 실패`와 `구조 실패`로 나눠 정리했습니다.

### 5.1 하드 실패: prompt-only 요청

| 케이스 | 결과 | 원인 | 해석 |
| --- | --- | --- | --- |
| `robot-arm-cobot-02` + TripoSR | 실패 | reference image 없음 | 모델의 입력 contract와 과제 요구를 혼동하면 안 된다는 점을 드러냄 |
| `conveyor-straight-01` + Hunyuan3D-2mini | 실패 | reference image 없음 | "Text/Image to 3D"라고 해도 선택 모델은 실제로 image-to-3D였음 |

이 실패는 모델 입력 contract와 직접 닿는 부분이라, UI와 runner에서 reference image 필요를 명시적으로 드러내는 쪽으로 설계했습니다.

### 5.2 구조 실패: 산업 자산 형태 보존 한계

| 케이스 | 관찰 | 왜 실패로 보는가 | 원인 추정 |
| --- | --- | --- | --- |
| TripoSR + robot arm | x축 bbox가 목표 대비 0.10배 | 관절 분절 구조보다 silhouette reconstruction에 치우침 | articulated geometry가 단일 표면으로 눌릴 가능성 |
| TripoSR + conveyor | 길이는 남지만 폭이 0.05배 수준 | 긴 직육면체 + 반복 roller를 안정적으로 분리하지 못함 | 얇고 반복적인 sub-part가 하나로 합쳐짐 |
| TripoSR + rack | bbox가 거의 cube에 가까움 | 랙의 본질인 bay repetition / vertical frame 구조가 사라짐 | front-view 이미지에서 깊이/층 구조 해석이 약함 |
| TripoSR + safety fence | panel thickness가 과장됨 | thin geometry가 두꺼운 mass로 바뀌어 simulator collision proxy로 부적합 | mesh panel을 세밀 구조가 아니라 면 덩어리로 재구성 |
| Hunyuan3D-2mini + AGV | 1.13M face / 20MB | shape fidelity는 높아도 simulator asset로는 너무 무거움 | 품질 우선 모델의 운영 비용 trade-off |

### 5.3 해석

이번 실험에서는 비교적 일관된 패턴이 나타났습니다.

- `TripoSR`은 빠르고 가볍지만 `얇은 구조`, `반복 구조`, `관절 구조`에서 약합니다.
- `Hunyuan3D-2mini`는 더 풍부한 형상을 주지만 `latency`와 `mesh density`가 커서 바로 simulator에 넣기엔 부담이 큽니다.
- 그래서 Track 1의 운영 전략은 TripoSR를 빠른 baseline, Hunyuan3D-2mini를 quality candidate로 두고, 후처리/decimation/quality gate를 다음 단계로 잡았습니다.

## 6. Track 3 결과

Track 3는 regex parser 한 겹이 아니라, downstream tool이 가져다 쓸 수 있는 scene interpretation tool 형태로 설계했습니다.

핵심 contract는 다음과 같습니다.

```text
parse_scene_to_scene_spec(user_instruction: str) -> SceneSpec
```

구현 포인트는 다음과 같습니다.

- `SceneSpec`, `SpaceSpec`, `EntitySpec`, `PlacementSpec`으로 schema-first 구조 설계
- `tool-schema` API 제공으로 function-calling contract 노출
- `deterministic_tool`, `llm_structured_output`, `hybrid_fallback` 3개 runtime 전략 지원
- parsed scene을 `scene_graph`와 `downstream_tasks`로 확장

### 6.1 과제 요구사항 대응

| 요구사항 | 대응 |
| --- | --- |
| 3개 이상 entity type | `agv`, `robot_arm`, `conveyor`, `rack`, `worker`, `charging_station`, `safety_fence`, `pallet_box` 지원 |
| 공간/수량/속성 파싱 | 공간 타입, 면적, 배치 패턴, near entrance, 회피 우선, speed profile 지원 |
| schema validation | Pydantic 기반 validation |
| 5개 입력 케이스 검증 | `data/scene_cases/text_to_scene_cases.json` + `pytest` |
| tool/function-calling 패턴 | `/api/scene/tool-schema` + structured output path |

### 6.2 구현상 의미 있었던 디테일

- `700평`을 `2314.05 m2`로 변환하면서 `area_source="700평"`를 남겨 환산 근거를 추적할 수 있도록 했습니다.
- `"6대 중 2대는 회피 우선"`을 `quantity=6`, `priority_quantity=2`, `mode=avoidance_priority`로 분리했습니다.
- LLM 경로(vLLM Qwen3.6 guided JSON, OpenAI structured output 호환)가 실패하더라도 deterministic parser로 fallback이 가능합니다.

### 6.3 검증 상태

- `pytest -q` -> `17 passed`
- `Track 3` 자체 케이스 5개 모두 validation 통과
- `llm_structured_output` 경로(OpenAI structured output + vLLM Qwen3.6 guided JSON)와 `hybrid_fallback` 경로 모두 테스트로 커버됩니다.

## 7. 주요 trade-off

1. 시연 중심 구성보다 `contract-first pipeline`을 선택했습니다.
   Track 3를 그 자체로 끝내지 않고, Track 1과 연결되는 downstream handoff 구조로 잡았습니다.

2. `pure LLM parser` 대신 `hybrid parser`를 선택했습니다.
   structured output은 표현력이 좋지만, 과제 데모 안정성을 위해 deterministic fallback을 남겨두는 것이 더 실무적이라고 판단했습니다.

3. `full simulator-specific postprocess` 대신 `uniform normalize + floor align`을 먼저 구현했습니다.
   Blender CLI가 없는 환경에서 재현성을 우선한 선택이었습니다.

4. text-to-3D 모델을 쓴 것처럼 보이게 하지 않았습니다.
   선택 모델이 image-to-3D 계열이라 reference image가 필요하다는 점을 문서와 UI에 그대로 적었습니다.

## 8. 한계와 다음 단계

현재 한계는 다음과 같습니다.

- Track 1은 reference image 의존성이 있습니다.
- Hunyuan 결과는 simulator asset로 쓰기 전에 decimation 단계가 필요합니다.
- normalize는 uniform scaling 기준이라 per-axis target fitting까지는 다루지 않습니다.
- Track 3의 downstream task는 planning skeleton까지이며 실제 layout generator/exporter는 미구현 상태입니다.

다음 단계는 다음과 같습니다.

1. Hunyuan 출력에 decimation / quality gate 추가
2. Track 3 -> asset queue -> layout generator 연결
3. reference image bootstrap용 provider 또는 retrieval layer 추가
4. simulator runtime(Unity/Isaac/TESSERACT)별 exporter 분기

## 9. 결론

이번 제출에서 가장 많이 고민한 부분은 두 트랙을 하나의 contract로 연결하는 방법이었습니다.

- Track 3: 자연어를 simulator-agnostic SceneSpec으로 바꾸는 해석 계층
- Track 1: 부족한 자산을 GLB로 보충하는 downstream generation tool

실험 결과도 같은 방향으로 정리되었습니다.

- TripoSR: 빠른 baseline
- Hunyuan3D-2mini: 더 무거운 quality candidate
- 실패 분석: 얇은 구조, 반복 구조, articulated structure가 어디서 무너지는지 확인

마무리 단계에서는 모델 실행 결과보다 TESSERACT에 연결 가능한 형태로 코드와 문서를 정리하는 데 더 시간을 썼습니다.
