# DreamCatcher Codex Reference

최종 갱신: 2026-05-13

이 파일은 작업 시작 전 반드시 확인해야 하는 기준 문서입니다.
루트 `README.md`는 안내판일 뿐이며, 제품 방향이나 구현 판단의 source of
truth가 아닙니다.

제품 방향, 구현 현황, 남은 과업, 로드맵, RunPod 정책, 모델, UI, RAW,
품질 자동화, release gate가 바뀌면 이 파일을 먼저 갱신합니다. 사용자에게
납품할 문서와 생성물은 `Product/`에 둡니다.

## 0. Every Task Rule

DreamCatcher에서 어떤 작업을 하든 아래 순서를 지킵니다.

- 작업 전: `PROJECT_FOUNDATION/README.md` 확인
- 작업 후: `PROJECT_FOUNDATION/README.md`와 `Product/` 갱신
- 매 작업마다: 검증 후 커밋

작업 후 갱신은 무조건 검토합니다. 기준, 운영, 사용, 빌드, RunPod, 모델, UI,
RAW, 품질 자동화, release, 납품물에 영향이 있으면 이 파일과 필요한
`Product/` 문서를 함께 고칩니다. 영향이 없으면 최종 보고에 갱신할 내용이
없었다고 명시합니다.

작업이 끝나면 관련 검증을 실행하고, 변경 범위를 확인한 뒤 하나의 일관된
커밋으로 남깁니다. 같은 작업의 문서, 코드, 테스트 변경은 가능하면 같은
커밋에 묶습니다.

구현 원칙:

- 하드코딩은 기본적으로 피합니다. 모델, GPU, RunPod template, storage, RAW 목표,
  품질 gate, UI 옵션처럼 운영 상황에 따라 바뀌는 값은 manifest, policy, schema,
  환경 변수, typed contract, catalog에서 읽도록 우선 설계합니다.
- UI의 작업 옵션은 고정 문자열 나열보다 현재 세션, 입력 파일, 모델 readiness,
  RunPod 상태, 품질 gate에 따라 동적으로 보이거나 비활성화되게 만듭니다.
- 하드코딩이 더 안전한 enum/contract인 경우에는 타입, 테스트, 문서로 의도를 남기고
  runtime policy와 분리합니다.
- Demo/mock/stub API는 runtime 앱과 release bundle 표면에 올리지 않습니다.
  실패, placeholder, 모델 미준비는 `pass`나 `ok=True`로 숨기지 않고 blocker,
  `suspicious`, readiness evidence, 또는 명시적 error로 드러냅니다.
- `seed_bundle/api_workflows` placeholder는 release/bootstrap blocker입니다.
  `verify_seed_bundle.py`, `setup.sh`, release preflight가 모두 실패해야 정상입니다.
- UI 변경은 텍스트, 텍스트박스, 버튼, 칩, 탭, 패널이 모바일/데스크톱에서 겹치거나
  깨지지 않는지 확인합니다. `auto-fit`, `minmax`, `min-width: 0`, 고정 비율,
  줄바꿈/말줄임, 충분한 높이를 우선 사용합니다.
- 설명성 메타 문구보다 실제 상용 서비스처럼 사용자가 바로 판단하고 누를 수 있는
  짧은 한글 문구를 씁니다.

## 1. 제품 기준

- 제품: 개인용 프로 사진 편집 Studio
- 사용자 진입점: ComfyUI가 아니라 DreamCatcher Studio
- 실행 엔진: ComfyUI는 Studio 뒤의 제어 가능한 backend engine
- 운영 방식: Ephemeral Zip Pod
- 공식 로컬 산출물: `Product/DreamCatcher.zip`
- RunPod 업로드명: `/workspace/DreamCatcher.zip`
- Pod 종료 원칙: outputs/evidence 회수 후 stop, terminate
- 장기 저장: Pod/Volume이 아니라 로컬 또는 외부 저장소

## 2. 문서와 산출물 구조

남기는 문서는 두 종류뿐입니다.

- Codex 기준 문서: `PROJECT_FOUNDATION/README.md`
- 실사용 검증 체크리스트와 단계별 리포트 양식:
  `PROJECT_FOUNDATION/RUNPOD_VALIDATION_CHECKLIST.md`
- 사용자 납품물: `Product/README.md`, `Product/USER_MANUAL.md`,
  `Product/BUILD_MANUAL.md`, 그리고 생성 산출물 `Product/DreamCatcher.zip`

문서를 새로 만들기보다 위 파일 중 하나를 갱신합니다. 상세 운영·사용·검증
절차 중 사용자가 실행할 납품 절차는 `Product/`에 두고, RunPod 실사용 smoke와
단계별 문제 보고 양식은 `PROJECT_FOUNDATION/RUNPOD_VALIDATION_CHECKLIST.md`에 둡니다.
개발 판단 기준은 이 파일에 통합합니다.

정합성 가드는 `app/backend/tests/test_project_handoff_contract.py`가 맡습니다.
이 테스트는 루트 README가 기준 문서처럼 커지지 않는지, Product 문서가 납품물로
유지되는지, release bundle manifest가 `Product/`와 이 파일을 바라보는지,
삭제된 문서 경로가 다시 참조되지 않는지 확인합니다.

## 3. Fresh Pull Handoff

어느 환경에서든 `git pull` 또는 fresh clone 뒤에는 아래 순서로 이어받습니다.

1. `README.md`를 보고 문서 위치만 확인합니다.
2. 개발 판단은 이 파일, `PROJECT_FOUNDATION/README.md`만 봅니다.
3. 사용자 납품·실행 절차는 `Product/` 문서만 봅니다.
4. `git status --short`로 로컬 변경이 있는지 확인합니다.
5. 로컬 의존성을 준비합니다.

```powershell
uv sync --project app\backend
npm ci --prefix app\frontend
```

6. 생성 산출물은 git에 없다고 가정합니다. 특히 `Product/DreamCatcher.zip`,
   `app/frontend/dist/`, `outputs/`, `app/runtime/`은 필요할 때 다시 만듭니다.
7. 작업 전 기준 검증은 아래 local gate를 따릅니다.
8. RunPod 작업은 항상 새 Pod, 새 bootstrap, outputs 회수 후 stop/terminate로
   이어갑니다.

## 4. RunPod 기준

- Template: private NVIDIA GPU Pod template
- GPU: `RTX PRO 6000`, `96GB VRAM`
- Primary image: `runpod/comfyui:1.4.1-cuda12.8`
- Compatibility alias: `runpod/comfyui:cuda12.8`
- Fallback image: `runpod/comfyui:1.3.0-cuda12.8`
- CUDA 13 image: live smoke 전까지 실험용
- Optional prewarmed image: `runpod/prewarm/Dockerfile.runtime`로 만든 private runtime image
- Prewarm 기본 범위: Python/Node/cache/custom node runtime만, 모델 weight와 사용자 output은 굽지 않음
- Container Disk: `80GB`
- Volume Disk: `400GB`, Full Frontier + Qwen judge 사용 시 `500GB`
- Network Volume: 기본 비활성화
- Persistent model cache: 사용하지 않음
- App root: `/workspace/DreamCatcher`
- ComfyUI root: `/workspace/runpod-slim/ComfyUI`
- Outputs: `/workspace/DreamCatcher/outputs`
- HF cache: `/workspace/.cache/huggingface`, session-local
- Ports: `8000/http` Studio, `8188/http` Comfy admin, `22/tcp` SSH

필수 환경 변수:

```text
HF_TOKEN=<accepted gated model licenses>
DC_MODEL_PROFILE=frontier
DC_SERVE_FRONTEND=1
DC_COMFY_PUBLIC=0
```

### 4.1 Cold-start 기준

현재 운영 정책은 Network Volume과 persistent model cache를 기본으로 쓰지 않습니다.
Pod를 terminate하면 `/workspace`, ComfyUI 모델 디렉터리, `/workspace/.cache/huggingface`가
다음 세션의 필수 상태로 남지 않는다고 가정합니다. 따라서 fresh Pod에서는 매번 아래 순서로
재수화합니다.

1. RTX PRO 6000 Pod 시작, ComfyUI CUDA 12.8 template 기동
2. `Product/DreamCatcher.zip` 업로드와 `/workspace/DreamCatcher` 압축 해제
3. ComfyUI root 정규화, backend/frontend 의존성 준비, seed/workflow 배치
4. `frontier` 기본 모델 세트 다운로드: BiRefNet, Qwen edit/2512/layered, Qwen judge,
   FLUX.2 Dev/Klein, FLUX.1 Fill, Z-Image, OmniGen2
5. frontend build, FastAPI Studio `8000`, ComfyUI `8188` 시작
6. storage/model/custom node/bootstrap contract evidence 생성
7. 필요 시 `runpod/start_qwen_judge.sh`로 Qwen judge vLLM 기동

시간 예산은 live smoke 전까지 추정치로 관리합니다.

- zip 업로드, 압축 해제, 앱 준비, 모델 다운로드 없음: `8-20 min`
- 일부 모델만 내려받는 디버그 bootstrap: `25-60 min`
- 공식 Full Frontier + Qwen judge fresh bootstrap: 보통 `60-150 min`
- HF/게이트 라이선스/네트워크가 느린 날: `2-4 h`까지 열어둠

병목은 거의 항상 모델 다운로드입니다. 두 번 이상의 실제 RTX PRO 6000 smoke에서
Full Frontier cold-start가 계속 `90 min`을 크게 넘으면 다음 최적화는 persistent Pod나
Network Volume이 아니라 custom prewarmed Docker image입니다. 그래도 장기 결과물은
계속 Pod 밖으로 회수합니다.

Prewarmed image 1차 구현은 runtime-only입니다. `runpod/prewarm/Dockerfile.runtime`와
`runpod/build_prewarmed_image.ps1`로 private image를 만들 수 있지만, `DreamCatcher.zip`은
계속 필수 업로드 산출물입니다. 이 이미지는 node/npm, uv/pip cache, 선택적 Comfy custom node
설치 시간을 줄이는 용도이며, HF token, 사용자 산출물, 기본 모델 weight는 넣지 않습니다.
모델 weight까지 굽는 단계는 라이선스, private registry 비용, 이미지 pull time을 live smoke로
확인한 뒤 별도 결정합니다.

## 5. 기술 스택

Frontend:

- React `19.2.6`
- React Compiler `1.0.0`
- Vite `8.0.11`
- TypeScript `6.0.3`
- `@tanstack/react-query`
- `zustand`
- `react-konva`
- `lucide-react`
- Radix primitives

Backend:

- Python 3.12
- `uv`
- FastAPI `0.136.1`
- Pydantic `2.13.4`
- Uvicorn `0.46.0`

RunPod에서는 `DC_SERVE_FRONTEND=1`일 때 FastAPI가 built frontend를 `8000`에서
서빙합니다. Vite dev server는 로컬 개발용입니다.

## 6. Studio UI 기준

첫 화면은 마케팅 페이지가 아니라 실제 편집 Studio입니다.

주 작업면:

- `원본`: 파일 추가, 입력 분석, 카메라/시작 경로 선택
- `RAW`: SingleRaw/TriRaw, merge/denoise, confidence/ghost/alignment evidence
- `편집`: cutout, background, fill/outpaint, relight, retouch, enhance
- `검수`: Qwen verdict, metric/checker, compare, retry, human approval
- `납품`: final save, preset, proofing sheet, package, batch delivery
- `운영`: RunPod state, queue, evidence/output recovery, stop/terminate

고정 레이아웃:

- compact top command bar
- icon/status 중심 work-surface tabs
- icon-first left tool rail
- center editor canvas
- right decision inspector
- bottom session/version/export/recovery strip
- advanced Frontier Stack operations surface

첫 진입 화면은 `원본 -> 분석 -> 시작` 흐름을 먼저 보여줍니다. backend notes나
구현 세부 문구를 그대로 노출하지 않고, 사용자가 바로 누를 수 있는 다음 작업
문구로 정리합니다.

금지:

- 모델 profile tab 재도입
- ComfyUI-first UX
- 카드만 길게 나열한 dashboard
- 사용자에게 설명하는 메타 문구
- 출력 회수 상태를 숨기는 UI
- 좁은 화면에서 텍스트박스, 버튼, 카드, 탭, 하단 strip이 서로 겹치는 레이아웃
- 운영 정책이나 모델 readiness를 UI 내부 상수로만 박아두는 구현

## 7. Frontier 모델 기준

공식 profile은 `frontier` 하나입니다. `core`, `pro`, `labs`는 한 릴리스 동안만
legacy alias로 받아 warning을 남기고 `frontier`로 매핑합니다.

| 작업 | 기본 후보 | 상태 |
| --- | --- | --- |
| Cutout | BiRefNet-DIS5K | ready |
| RAW decode/prep | SingleRaw, TriRaw runtime | ready |
| RAW frontier eval | `tri_raw_frontier_v1` | ready |
| Learned RAW adapter | RawFusion-style optional hook | workflow_needed |
| Precision edit/text edit | Qwen-Image-Edit-2511 + Lightning | ready |
| Image generation | Qwen-Image-2512 | ready |
| Local quality judge | Qwen3.6-35B-A3B-FP8 | ready |
| Layered edit | Qwen-Image-Layered FP8 | ready |
| Composition | FLUX.2 Dev FP8 + Flux2TurboComfyv2 | ready |
| Preview/relight | FLUX.2 Klein FP8 + IC-Light + Depth Anything | ready |
| Fill/inpaint/outpaint | FLUX.1 Fill dev | ready |
| Fast candidate | Z-Image-Turbo/Edit | ready |
| Unified edit research | OmniGen2 | ready |
| Aggressive edit research | LongCat-Image-Edit-Turbo | weights_pending |
| Reference edit research | FLUX.1 Kontext-dev | workflow_needed |

## 8. RAW 기준

- `tri_raw_baseline_v1`: 현재 안정 fallback
- `tri_raw_frontier_v1`: 3-frame RAW의 evidence-rich 계약
- 현재 Studio 자동 intake의 공식 RAW 입력은 단일 RAW와 3-frame RAW bracket입니다.
- rawprep engine 계약은 3-frame과 9-frame RAW를 허용합니다.
- 9-frame burst/HDR은 NTIRE 계열 연구용 optional path이며, Studio 기본 UX 승격 전에는
  명시적 rawprep/API/benchmark 경로로만 검증합니다.
- 출력 evidence: merged HDR, denoised result, confidence map, ghost map,
  alignment evidence, model/bootstrap evidence
- RAW 결과 목표는 `truth_preserving` 기본값과 `aggressive_restore` 옵션으로 나눕니다.
- `truth_preserving`: ghost/noise를 줄이되 없는 디테일을 만들지 않는 기본 납품 경로
- `aggressive_restore`: 강한 denoise, deblur, learned restoration, perceptual detail reconstruction
  후보를 시도하되 Qwen/metric/golden review와 사람 승인을 거치는 선택 경로
- RAW 목표의 사용자 문구와 review gate는 `app/models/model_manifest.yaml`의
  `raw_frontier.restoration_goals`에서 파생되고, Studio는
  `/api/rawprep/restoration-goals` 정책을 받아 UI를 그립니다. UI에서 목표 선택지를
  별도 고정 배열로 운영하지 않습니다.
- `restoration_goal`은 Studio intake, rawprep request, `RawPrepJobPlan`, TriRaw runtime report,
  diagnostics manifest까지 같은 값으로 전달됩니다.
- Studio UI의 `RAW 결과 목표`에서 `진실 보존`과 `공격적 복원 후보`를 선택합니다.
- `aggressive_restore`를 선택하면 `aggressive_restore_preview.jpg` 후보를 만들고
  `requires_review`, `delivery_default=false`, Qwen/metric/golden/human approval gate를
  candidate score와 report에 남깁니다.
- RawFusion-style learned adapter는 명시적 env가 있을 때만 사용
- learned adapter 실패는 숨기지 않고 baseline으로 fallback

첫 acceptance는 단순 화질 주장보다 진단 가능성입니다. Studio는 alignment
confidence, ghost risk, fallback reason을 설명해야 합니다. 공격적 복원은 더 선명해 보여도
hallucinated detail 위험이 있으므로 납품 기본값이 아니라 검수 대상 후보로 취급합니다.

## 9. 데이터와 연구 기준

수집한 연구/데이터는 문서 링크로만 남기지 않습니다.

- `seed_bundle/frontier_dataset_manifest.yaml`: 연구/데이터 catalog
- `frontier_dataset_catalog.py`: backend catalog
- `frontier_dataset_activation.py`: Studio task와 catalog 연결
- `frontier_dataset_plan.py`: 다운로드 없는 local collection plan 생성

기본 bootstrap은 모든 dataset을 다운로드하지 않습니다. 큰 corpora는
`local_data_lab/cache/` 아래 local-only로 관리하고, compact runtime prior만
`seed_bundle/runtime_priors/`로 승격합니다.

추적 영역:

- RAW merge/denoise/restoration: NTIRE Burst HDR, RASD, RawFusion,
  BracketIRE/IREANet, RAWIR, SIDD, SID
- Background removal/matting: DIS5K, BiRefNet-DIS5K, SA-1B, COCO-Stuff, ADE20K
- Edit/fill/background: MagicBrush, ImgEdit, EditBench, Places2, LaMa

## 10. 품질 자동화와 튜닝 기준

품질 자동화는 `Qwen + metric/checker + golden runner + 사람 승인` 구조입니다.

- Local judge: `Qwen/Qwen3.6-35B-A3B-FP8`
- Cloud fallback: disabled
- Automation version: `quality_automation_v2`
- Qwen response schema: `qwen_judge_signal_v2`
- Qwen input evidence: `judge_evidence_packet_v1`
- Golden calibration: `golden_calibration_v1`
- Verdicts: `pass`, `suspicious`, `fail`
- `suspicious`: 항상 사람 승인 필요
- Quality artifacts: `outputs/_quality_automation/assessments/`
- Tuning proposals: `outputs/_quality_automation/tuning_proposals/`

Qwen v2 응답은 아래 축을 포함합니다.

- `axis_scores`: intent match, technical quality, aesthetic quality,
  subject preservation, mask boundary, color naturalness
- `localized_issues`: 문제 영역, 실패 유형, 심각도, 근거, 선택적 normalized bbox
- `correction_plan`: 노출, 대비, 암부, 하이라이트, 색온도, 틴트, 채도,
  denoise/edit strength, crop 후보
- `rationale`, `retry_instruction`, `work_instruction`

Qwen이 판단할 때 받는 증거는 `judge_evidence_packet_v1`로 묶습니다.

- deterministic image metrics와 before/after delta
- task intent와 operation context
- mask evidence
- RAW confidence/ghost/alignment evidence
- workflow/model/bootstrap evidence
- user preference memory
- golden context와 재생해야 할 golden case

Qwen이 제안한 수치 보정값은 바로 적용하지 않습니다. metric/checker와 합쳐
assessment artifact에 남긴 뒤 `golden_quality_calibration.seed.json` 기준으로
confidence와 verdict를 보정합니다. suspicious/fail, 낮은 confidence, golden 보정
조정은 사람 승인과 golden runner를 거칩니다.

자동 허용:

- 품질 검사
- 실패 태그
- 재시도 지시
- evidence packet 생성
- golden score calibration
- 후보 비교
- golden session replay
- tuning proposal 초안

사람 승인 필수:

- preset 변경
- workflow 변경
- prompt/rubric 변경
- metric threshold 변경
- code-level tuning
- release promotion

## 11. Benchmark 기준

Benchmark 계약은 문서가 아니라 JSON을 기준으로 둡니다.

- `benchmark/BENCHMARK_CATALOG.json`
- `benchmark/SINGLE_RAW_GOLD_SET_MANIFEST.json`
- `benchmark/TRI_RAW_BUCKET_SAMPLE_MANIFEST.json`

Local sample media는 `benchmark/samples/` 아래에 둘 수 있지만 release zip에는
포함하지 않습니다. `benchmark/BENCHMARK_SAMPLE_LIBRARY.json`도 local/generated로
취급하며 zip에 넣지 않습니다.

## 12. Release bundle 기준

Release bundle은 fresh Pod bootstrap에 필요한 파일만 포함합니다.

포함:

- `app/`
- `runpod/`
- `seed_bundle/`
- `benchmark/`의 JSON 계약
- `PROJECT_FOUNDATION/README.md`
- `Product/*.md`
- 루트 `README.md`
- `.gitattributes`, `.gitignore`

제외:

- `.git/`, `.venv/`, caches
- `app/frontend/node_modules/`
- `app/frontend/dist/`
- `app/runtime/`, `app/logs/`, `app/workflows/runtime/`
- `outputs/`, `archives/`, `benchmarks/`
- `benchmark/samples/`
- `local_data_lab/cache/`, `runs/`, `exports/`, `logs/`
- `DreamCatcher.zip`, `Product/DreamCatcher.zip`

`test_project_handoff_contract.py`는 위 생성 산출물이 git에 다시 추적되지 않는지
검사합니다. 특히 `app/runtime/`의 bootstrap/healthcheck JSON은 smoke evidence일 뿐
저장소 source of truth가 아닙니다.

## 13. 현재 release gates

Local gate:

```powershell
uv run --directory app\backend pytest
npm run typecheck --prefix app\frontend
npm run build --prefix app\frontend
python app\scripts\verify_seed_bundle.py --seed-root seed_bundle
uv run --project app\backend python runpod\preflight_release_bundle.py
```

`verify_seed_bundle.py`는 placeholder API workflow가 있으면 실패해야 합니다.
`/demo/*` 같은 mock API surface는 기본 앱과 release bundle에 포함하지 않습니다.

RunPod gate:

1. Fresh RTX PRO 6000 Pod
2. Upload `/workspace/DreamCatcher.zip`
3. Bootstrap `--profile frontier`
4. Verify Studio, Comfy health, model contracts, RAW evidence, quality automation
5. Export package
6. Recover outputs/evidence
7. Stop and terminate Pod

아직 남은 release evidence:

- Fresh RunPod Frontier smoke
- Live Qwen judge smoke
- 실제 RAW sample 기준 baseline/frontier 품질 비교
- UI 한글 문자열 source scan과 첫 화면 브라우저 검증 완료, 남은 화면별 polish 확인
- UI 겹침/깨짐 회귀 확인: 주요 작업면을 데스크톱/태블릿/모바일 폭에서 브라우저로 확인
- 하드코딩 회귀 확인: 운영 정책과 모델/RAW/품질 옵션이 manifest/policy/contract에서
  파생되는지 코드 리뷰

## 14. 구현 현황과 로드맵

이 섹션은 fresh `git pull` 뒤 다음 작업자가 지금 상태와 다음 과업을 바로
이어받기 위한 현황판입니다.

| 영역 | 현재 구현 | 남은 과업 | 구현 주안점 |
| --- | --- | --- | --- |
| 문서 구조 | 기준 문서는 `PROJECT_FOUNDATION/README.md` 하나로 통합, 납품 문서는 `Product/`로 정리 | 변경 때마다 이 파일과 필요한 `Product/` 문서만 갱신 | 문서를 늘리지 말고 기존 기준/납품 문서 안에서 정제 |
| Product bundle | `Product/DreamCatcher.zip` 기본 생성, preflight 통과 | fresh 환경마다 zip 재생성, RunPod 업로드 검증 | zip은 git에 넣지 않고 preflight 결과로만 생성 |
| RunPod baseline | RTX PRO 6000, CUDA 12.8 ComfyUI image, ephemeral storage 정책 고정 | 실제 fresh Pod smoke evidence 확보 | Pod 상태에 의존하지 않고 outputs 회수 후 terminate |
| Runtime prewarm | `runpod/prewarm/Dockerfile.runtime`, `runpod/build_prewarmed_image.ps1`, template policy metadata 구현 | private registry build/push, RTX PRO 6000 smoke에서 시간 절감 실측 | source of truth는 zip, 모델 weight는 기본 bake 금지 |
| Studio UI | 작업면 `원본/RAW/편집/검수/납품/운영`, icon/status work-surface tabs, `원본 -> 분석 -> 시작` 세션 흐름, RAW 결과 목표 선택, tool rail, canvas, inspector, bottom strip 구현 | 실제 파일 업로드/RAW/편집/검수 화면별 브라우저 polish, 전체 UI string locale 정리 | 상용 편집앱처럼 작업 흐름 중심, 설명성 메타 문구 제거 |
| Frontier model stack | `frontier` 단일 profile, model manifest/status, bootstrap contract 정리 | 각 live workflow smoke, workflow_needed/weights_pending 항목 해소 | profile split 금지, task별 model readiness를 명확히 표시 |
| RAW frontier | `tri_raw_baseline_v1`, `tri_raw_frontier_v1`, `tri_raw_frontier_eval_v1`, `restoration_goal` 계약, `truth_preserving` 기본 결과, `aggressive_restore_preview.jpg` 검수 후보와 evidence export 구현 | 실제 RAW sample 비교, learned adapter 실험, 9-frame 연구 경로 검증, 공격적 복원 후보 검수 | 화질 주장보다 confidence/ghost/alignment/fallback 근거 우선, aggressive restore는 hallucination risk를 명시 |
| Dataset activation | `frontier_dataset_manifest`, catalog, activation, plan script 연결 | local data subset 수집, license 확인, 평가/fine-tune 후보 구성 | default bootstrap에서 대형 dataset 다운로드 금지 |
| 품질 자동화 | Qwen judge 정책, `judge_evidence_packet_v1`, metric/checker fusion, `golden_calibration_v1`, assessment/tuning proposal API와 artifact 경로 구현 | live Qwen judge smoke, 실제 golden sample population, golden session runner 강화, human approval queue 고도화 | 증거를 먼저 모으고 golden 보정 후 판단, 자동 코드 변경 금지, proposal-only와 회귀 검증 유지 |
| Benchmark | JSON catalog/manifests 기준으로 전환, 사람용 md spec 제거 | 실제 sample population, measured evidence 축적 | benchmark는 release 주장 근거이지 장식 문서가 아님 |
| Release readiness | local pytest/typecheck/build/seed/preflight 통과 경험 있음 | fresh RunPod Frontier smoke, output recovery, terminate evidence | "로컬 통과"와 "Hosted release ready"를 구분 |

우선순위:

1. Fresh RunPod smoke를 실행하고 `PROJECT_FOUNDATION/RUNPOD_VALIDATION_CHECKLIST.md` 기준으로
   evidence를 남깁니다.
2. Runtime prewarmed image를 private registry에 build/push하고 cold-start 절감 시간을 실측합니다.
3. UI 작업면별 UX polish를 실제 파일 업로드/RAW/편집/검수 케이스로 브라우저 검증합니다.
4. RAW 실제 sample set을 채워 baseline/frontier 비교 evidence를 만듭니다.
5. Qwen local judge를 RunPod에서 live smoke하고 품질 자동화 artifact를 회수합니다.
6. model/workflow gap을 `workflow_needed`, `weights_pending`, `license_review`에서
   `ready`로 하나씩 승격합니다.

완료 기준:

- fresh clone 또는 `git pull` 뒤 이 파일과 `Product/` 문서만 보고 작업을 이어갈 수 있음
- `Product/DreamCatcher.zip`을 새로 만들어 fresh Pod에서 bootstrap 가능
- outputs, RAW evidence, quality artifacts, bootstrap evidence가 termination 전에 회수됨
- 남은 과업은 위 표의 "남은 과업"과 우선순위 목록에서 추적 가능
