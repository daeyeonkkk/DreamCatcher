# DreamCatcher Build Manual

최종 갱신: 2026-05-13

## 1. 현재 기준

- 제품: 개인용 프로 사진 편집 Studio
- 공식 산출물: `Product/DreamCatcher.zip`
- RunPod 업로드명: `/workspace/DreamCatcher.zip`
- 모델 프로필: `frontier`
- GPU: `RTX PRO 6000`, `96GB VRAM`
- 이미지: `runpod/comfyui:1.4.1-cuda12.8`
- fallback 이미지: `runpod/comfyui:1.3.0-cuda12.8`
- Studio 포트: `8000/http`
- ComfyUI 관리자 포트: `8188/http`, 필요할 때만 공개

## 2. RunPod 저장소 정책

- Container Disk: `80GB`
- Volume Disk: `400GB`
- Full Frontier + Qwen judge: `500GB`
- Network Volume: 기본 비활성화
- Persistent model cache: 사용하지 않음
- 장기 보관: 로컬 또는 외부 저장소
- Pod 종료 전: outputs와 evidence 회수

## 3. 로컬 준비

```powershell
cd C:\my_project\DreamCatcher
uv sync --project app\backend
npm ci --prefix app\frontend
```

## 4. 로컬 검증

```powershell
cd C:\my_project\DreamCatcher
uv run --directory app\backend pytest
npm run typecheck --prefix app\frontend
npm run build --prefix app\frontend
python app\scripts\verify_seed_bundle.py --seed-root seed_bundle
uv run --project app\backend python runpod\preflight_release_bundle.py
```

`verify_seed_bundle.py`가 placeholder workflow를 보고하면 그대로 실패로 처리합니다.
데모/mock API나 mock ComfyUI 파일은 zip에 들어가면 안 됩니다.

preflight가 통과하면 기본 위치에 생성됩니다.

```text
C:\my_project\DreamCatcher\Product\DreamCatcher.zip
```

## 5. Zip 구성 원칙

`DreamCatcher.zip`에는 fresh Pod bootstrap에 필요한 코드, seed bundle, workflow, 기준 문서, Product 문서만 들어갑니다.

포함:

- `app/`
- `runpod/`
- `seed_bundle/`
- `benchmark/`의 JSON 계약 파일
- `PROJECT_FOUNDATION/README.md`
- `Product/*.md`
- 루트 `README.md`

제외:

- `.git/`
- `.venv/`
- `app/frontend/node_modules/`
- `app/frontend/dist/`
- `app/runtime/`
- `app/logs/`
- `outputs/`
- `benchmark/samples/`
- `local_data_lab/cache/`, `runs/`, `exports/`, `logs/`
- 이전에 생성한 zip 파일

## 6. RunPod 업로드와 압축 해제

RunPod에 `Product/DreamCatcher.zip`을 업로드하되, Pod 안에서는 아래 위치가 되게 합니다.

```text
/workspace/DreamCatcher.zip
```

압축 해제:

```bash
cd /workspace
python3 - <<'PY'
from pathlib import Path
import zipfile

with zipfile.ZipFile(Path("/workspace/DreamCatcher.zip"), "r") as zf:
    zf.extractall("/workspace")
PY
```

## 7. Bootstrap

```bash
export HF_TOKEN=hf_xxx
export DC_MODEL_PROFILE=frontier
export DC_SERVE_FRONTEND=1
export DC_COMFY_PUBLIC=0

bash /workspace/DreamCatcher/runpod/bootstrap.sh --profile frontier
```

bootstrap은 `seed_bundle/api_workflows`가 실제 ComfyUI API export가 아니면 실패합니다.

기존 seed를 강제로 다시 풀어야 할 때:

```bash
bash /workspace/DreamCatcher/runpod/bootstrap.sh --profile frontier --force-reseed
```

개별 모델 다운로드가 필요할 때:

```bash
bash /workspace/DreamCatcher/runpod/bootstrap.sh --download-birefnet
bash /workspace/DreamCatcher/runpod/bootstrap.sh --download-qwen
bash /workspace/DreamCatcher/runpod/bootstrap.sh --download-qwen-2512
bash /workspace/DreamCatcher/runpod/bootstrap.sh --download-qwen-judge
bash /workspace/DreamCatcher/runpod/bootstrap.sh --download-flux2-dev
bash /workspace/DreamCatcher/runpod/bootstrap.sh --download-klein
bash /workspace/DreamCatcher/runpod/bootstrap.sh --download-fill
bash /workspace/DreamCatcher/runpod/bootstrap.sh --download-qwen-layered
bash /workspace/DreamCatcher/runpod/bootstrap.sh --download-z-image
bash /workspace/DreamCatcher/runpod/bootstrap.sh --download-omnigen2
```

## 8. Cold-start 예상

DreamCatcher는 Ephemeral Zip Pod 기준입니다. 새 Pod는 이전 세션의 모델 cache나
workspace 상태에 기대지 않으므로, `--profile frontier`를 실행하면 매번 앱과 모델을 새로
재수화합니다.

기본 흐름:

1. RTX PRO 6000 Pod 시작
2. `/workspace/DreamCatcher.zip` 업로드와 압축 해제
3. ComfyUI root, seed bundle, backend/frontend 준비
4. Frontier 모델 다운로드
5. Studio, ComfyUI, runtime contract 확인
6. 필요 시 Qwen judge vLLM 시작

예상 시간:

- 모델 다운로드가 없는 재실행: `8-20 min`
- 일부 모델만 받는 디버그 bootstrap: `25-60 min`
- Full Frontier + Qwen judge fresh bootstrap: 보통 `60-150 min`
- HF, gated license, 네트워크가 느린 경우: `2-4 h`

가장 큰 변수는 모델 다운로드입니다. cold-start가 반복적으로 길어지면 다음 최적화는
Network Volume이 아니라 custom prewarmed Docker image입니다.

## 9. Runtime prewarmed image

기본 RunPod image는 계속 `runpod/comfyui:1.4.1-cuda12.8`입니다. 다만 cold-start 실측에서
앱 준비 시간이 반복적으로 부담되면 private runtime image를 먼저 씁니다.

```powershell
cd C:\my_project\DreamCatcher
.\runpod\build_prewarmed_image.ps1 `
  -ImageTag <private-registry>/dreamcatcher-runtime-prewarm:cuda12.8-frontier
```

Custom node까지 image에 미리 넣어 smoke하려면 아래처럼 실행합니다.

```powershell
.\runpod\build_prewarmed_image.ps1 `
  -ImageTag <private-registry>/dreamcatcher-runtime-prewarm:cuda12.8-frontier `
  -PrewarmCustomNodes
```

Push가 필요하면 `-Push`를 붙입니다. RunPod Template에서 이 private image를 쓰더라도
`/workspace/DreamCatcher.zip` 업로드와 `--profile frontier` bootstrap은 그대로 필요합니다.
이 image는 runtime cache 최적화용이며 모델 weight, `HF_TOKEN`, 사용자 output을 굽지 않습니다.

사용한 private image는 환경 변수로 기록합니다.

```bash
export RUNPOD_TEMPLATE_PREWARMED_IMAGE=<private-registry>/dreamcatcher-runtime-prewarm:cuda12.8-frontier
export DC_PREWARMED_IMAGE=runtime-v1
```

## 10. 상태 확인

```bash
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/api/rawprep/health
curl -s http://127.0.0.1:8000/api/runpod/model-profiles
curl -s http://127.0.0.1:8000/api/runpod/template-policy
curl -s http://127.0.0.1:8000/api/runpod/bootstrap-session
curl -s http://127.0.0.1:8188/system_stats
```

주요 evidence:

```text
/workspace/DreamCatcher/app/runtime/bootstrap_summary.json
/workspace/DreamCatcher/app/runtime/runpod_model_bootstrap_contract.json
/workspace/DreamCatcher/app/runtime/runpod_storage_contract.json
/workspace/DreamCatcher/app/runtime/runpod_custom_node_contract.json
```

## 11. Qwen 품질 판단

Live judge가 필요할 때만 실행합니다.

```bash
cd /workspace/DreamCatcher
bash runpod/start_qwen_judge.sh
```

Cloud fallback은 사용하지 않습니다.

품질 판단 artifact에는 아래 항목이 함께 남습니다.

- `qwen_judge_signal_v2`: Qwen의 판정, 축별 점수, 문제 영역, 보정 제안
- `judge_evidence_packet_v1`: Qwen이 받은 작업 의도, 지표, 마스크/RAW/workflow/선호/golden 근거
- `golden_calibration_v1`: golden 기준으로 보정된 verdict, confidence, replay case

Golden calibration seed는 `seed_bundle/runtime_priors/evaluator/golden_quality_calibration.seed.json`입니다.

## 12. RAW 복원 목표 검증

TriRaw 요청에는 `restoration_goal`이 들어갑니다.

- 기본값: `truth_preserving`
- 공격적 후보: `aggressive_restore`

Studio의 `RAW 결과 목표` 선택지는 `/api/rawprep/restoration-goals`에서 읽습니다.
이 정책은 `app/models/model_manifest.yaml`의 `raw_frontier.restoration_goals`를 기준으로
하며, 사용자 화면에는 한글 문구로 표시되어야 합니다.

`aggressive_restore` 실행 후에는 group report와 diagnostics manifest에서 아래 항목을 확인합니다.

- `restoration_goal=aggressive_restore`
- `aggressive_restore_candidate_path`
- candidate score의 `requires_review=true`
- `delivery_default=false`
- Qwen/metric/golden/human approval gate

공격적 복원 후보는 검수 전 납품 기본값으로 쓰지 않습니다.

## 13. 종료

1. Studio에서 최종 이미지와 패키지를 저장합니다.
2. `/workspace/DreamCatcher/outputs`를 회수합니다.
3. 필요한 evidence를 함께 보관합니다.
4. Pod를 stop합니다.
5. Pod를 terminate합니다.
