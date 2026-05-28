# RETROSPECTIVE

## 1. 이번 과제에서 정한 우선순위

이번 과제에서는 눈에 띄는 데모보다 다음 단계로 이어지는 구조를 남기는 쪽에 더 무게를 두었습니다.

과제 문서를 읽고 나서 저는 다음과 같이 해석했습니다.

- Track 3는 PPT 슬라이드 8의 Tool-calling, Scene Graph 확장성 언급을 보고, 작은 JSON parser보다 Text-to-Simulation 입력 해석 레이어로 설계해야 한다고 봤습니다.
- Track 1도 슬라이드 4의 후처리·실패 분석 요구를 보고, 단순 모델 실행보다 시뮬레이션 자산으로 정리하는 단계가 더 비중 있다고 판단했습니다.

이 해석에 따라 결과물을 두 개의 독립 데모가 아니라 하나의 시스템으로 연결해 설명하는 방향을 잡았습니다.

## 2. 가장 큰 의사결정과 trade-off

### 2.1 Track 1 + Track 3를 하나의 스토리로 묶었습니다

선택지는 두 가지였습니다.

1. Track 1과 Track 3를 각각 완성된 미니 앱처럼 보이게 만들기
2. Track 3를 입력 해석 계층, Track 1을 downstream asset tool로 두고 같은 pipeline 안에 넣기

저는 2번을 택했습니다.

이유:

- 제가 PPT를 읽고 이해한 TESSERACT 흐름은 "자연어 -> 씬 명세 -> 필요한 자산 -> 시뮬레이션"이었습니다. 이 흐름에서는 Track 3의 출력이 Track 1의 입력 일부가 됩니다.
- Track 3만 단독으로 두면 downstream tool이 비어 있는 상태가 됩니다.

trade-off:

- 각 트랙을 개별 데모로 보여주는 임팩트는 줄었습니다. Gradio 두 개로 분리했다면 시연은 더 단순했을 것입니다.

### 2.2 pure LLM이 아니라 hybrid parser를 택했습니다

처음에는 Track 3를 전부 LLM structured output으로 처리하는 방향도 가능했습니다. 하지만 최종적으로는 LLM 구조화 출력(로컬 vLLM Qwen3.6 guided JSON 기본, OpenAI structured output 호환) + deterministic fallback 구조로 갔습니다.

이유:

- 과제의 평가 포인트는 구조화 출력, tool/function-calling 이해, edge case 처리입니다.
- pure LLM은 표현력은 좋지만 데모 안정성이 약합니다.
- pure rule parser는 재현성은 좋지만 확장성이 약합니다.

그래서 `LLM이 잘하는 것`과 `rule이 잘하는 것`을 나누었습니다.

- LLM: 문장 해석, 모호한 구조화
- rule: fallback, 기본값, alias 정규화

trade-off:

- 구현 복잡도가 올라갔습니다. 두 경로의 결과가 어긋날 때를 다루는 정규화 단계가 따로 필요했습니다.

### 2.3 모델 한계를 숨기지 않았습니다

Track 1에서는 image-to-3D 모델을 text-to-3D처럼 보이게 설명할 수도 있었지만, 그렇게 접근하지 않았습니다.

이유:

- 선택 모델인 TripoSR, Hunyuan3D-2mini는 실제로 image-to-3D 계열입니다.
- 이 부분을 두루뭉술하게 적으면 평가자가 모델 입력 contract를 확인하기 어렵다고 봤습니다.

그래서 UI, API, 문서에 모두 reference image 필요를 명시했습니다.

trade-off:

- 데모에서 image upload 단계가 추가되어 클릭이 한 번 늘었습니다.

### 2.4 Next.js를 선택하고 Gradio는 포기했습니다

빠르게 데모만 만들려면 Gradio가 더 쉬웠습니다. 그래도 최종 UI는 Next.js로 갔습니다.

이유:

- 과제 문서에서 UI 톤 정렬을 분명히 요구했습니다.
- card-based layout, navy/amber tone, 2~3 column 구조는 Next.js + Tailwind가 더 잘 맞습니다.
- Track 1과 Track 3를 분리된 페이지로 유지하면서도 전체 랜딩 구조를 잡기 쉽습니다.

trade-off:

- 초기 구현 속도가 느려졌습니다. Gradio였다면 첫 화면이 하루 빨리 나왔을 것입니다.

### 2.5 postprocess는 full pipeline이 아니라 conservative pipeline으로 갔습니다

처음에는 decimation, texture baking, scale fitting까지 전부 욕심낼 수 있었습니다. 하지만 최종적으로는 `GLB 통일 + uniform scale normalization + floor alignment + mesh metrics`에 집중했습니다.

이유:

- Blender CLI가 없는 환경에서 과도한 후처리를 약속하면 재현성이 떨어집니다.
- 시뮬레이션 관점에서 가장 먼저 필요한 것은 topology editing보다 `파일 통일`, `바닥 정렬`, `크기 기준`, `메트릭 수집`이었습니다.

trade-off:

- decimation까지 자동화하지 못해 Hunyuan 출력은 그대로는 무겁습니다.

## 3. 이번 과제에서 배운 점

### 3.1 산업 자산에서는 메시 품질보다 구조 보존이 더 걸립니다

사람이나 동물형 자산과 달리, 산업 자산에서는 다음 요소가 특히 중요했습니다.

- 반복 구조가 유지되는가
- 얇은 구조가 뭉개지지 않는가
- 기능적 sub-part가 분리되는가

이번 실험에서 TripoSR는 빠르고 가볍지만 rack, conveyor, safety fence에서 이런 구조적 보존이 약했습니다. 반대로 Hunyuan3D-2mini는 더 풍부한 볼륨을 주지만 simulator asset로 쓰기엔 너무 무거운 메시를 만듭니다.

"좋은 모델"의 기준이 시각 품질만이 아니라 도메인 용도에서의 실패 양상까지 포함한다는 점은 직접 돌려보고 나서야 분명해졌습니다.

### 3.2 Track 3에서 결국 시간을 더 쓴 곳은 contract 쪽이었습니다

처음에는 자연어를 JSON으로 바꾸는 parser 문제로 잡고 시작했습니다. 막상 진행해 보니 parser 자체보다 그 뒤의 contract 설계가 더 손이 갔습니다.

어떤 필드를 남겨야 downstream tool이 쓸 수 있을지 정해야 했습니다.

- quantity
- placement
- priority_quantity
- assumptions
- warnings
- required_asset_types

이런 구조가 없으면 자연어를 JSON으로 바꿔도 실제 시스템에는 연결되지 않습니다.

그래서 Track 3에서는 parser보다 SceneSpec 설계에 시간을 더 썼습니다.

### 3.3 후처리에서 잡은 버그 하나

중간에 발견한 버그는 Scene transform을 metrics가 무시해서 normalize 결과가 bbox에 반영되지 않던 문제였습니다. UI 데모만 보고 있었다면 지나치기 쉬운 부분이었습니다.

이 일을 겪고 나서 후처리와 검증 레이어를 더 챙기게 되었습니다.

## 4. 아쉬웠던 점

### 4.1 text-to-3D까지 확장하지 못했습니다

개인적으로는 Track 1이 prompt-only asset bootstrap으로 확장되는 방향에 관심이 있었지만, 이번 제출에서는 거기까지 가지 않았습니다. 선택한 모델이 image-to-3D 계열이라 입력 contract부터 맞추는 데 시간이 먼저 들었기 때문입니다.

### 4.2 simulator export까지는 들어가지 못했습니다

Track 3의 downstream task에는 `layout_generation`, `simulation_export`, `scene_validation`을 남겨두었지만 실제 exporter는 구현하지 않았습니다.

exporter는 구현하지 못했지만, 그 자리를 비워둔 채로 어떤 contract로 연결될지는 SceneSpec 쪽에 남겨두었습니다.

## 5. 시간이 더 있었다면

우선순위를 다음과 같이 정리했습니다.

1. Hunyuan3D-2mini 출력에 decimation / quality gate 추가 — 1M+ face 출력이 simulator로 바로 갈 수 없는 상태라 가장 시급했습니다.
2. Track 3 → asset queue → layout generator 연결 — Track 3 SceneSpec이 이미 downstream_tasks 필드를 가지고 있어서 다음 단계가 비교적 명확했습니다.
3. reference image bootstrap layer 추가 — image-to-3D 의존을 줄이려면 필요했습니다.
4. simulator별 exporter 분기 — 가장 마지막에 둔 이유는, exporter는 위 세 단계가 정리된 뒤에야 의미가 있기 때문입니다.

## 6. 최종적으로 남긴 것

이번 과제에서 남기고 싶었던 부분은 다음과 같습니다.

- Track 3를 agent tool contract 형태로 설계한 점
- Track 1을 모델 실행이 아니라 simulator-ready asset pipeline으로 정리한 점
- 실패 케이스를 숨기지 않고, 그 실패가 산업 자산 도메인에서 어떤 의미인지 같이 적은 점

코드 구조, 문서, 실패 분석, UI 방향을 같은 결정 기준으로 이어가는 데 가장 시간을 썼습니다.
