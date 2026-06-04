# DreamCatcher RunPod Validation Checklist

최종 갱신: 2026-05-13

이 파일은 DreamCatcher 실사용 RunPod smoke의 체크리스트이자 단계별 리포트 양식입니다.
각 단계는 `PASS`, `BLOCKED`, `FAIL`, `QUESTION` 중 하나로 보고합니다. 문제가 생기면
다음 단계로 넘어가지 말고 해당 단계 리포트와 로그를 남긴 뒤 판단을 요청합니다.

## 0. 리포트 방식

공통 리포트:

```text
[DreamCatcher 실사용 테스트 리포트]

단계:
상태: PASS / BLOCKED / FAIL / QUESTION
시작 시각:
소요 시간:
환경:
- GPU:
- Image:
- Container Disk:
- Volume Disk:
- Network Volume:
- Pod ID 또는 이름:

실행한 명령:
붙여넣기:

결과 요약:
- 성공한 것:
- 이상한 것:
- 실패한 것:

증거:
- 스크린샷:
- 생성 파일 경로:
- 로그 마지막 80줄:
- artifact 경로:

내 판단이 필요한 질문:
```

긴급 리포트:

```text
단계:
상태:
마지막으로 실행한 명령:
에러 로그 마지막 80줄:
생성된 artifact 경로:
지금 Pod를 유지해야 하는가, 종료해도 되는가:
```

민감값은 붙이지 않습니다. 예: `HF_TOKEN=hf_***`.

## 1. Pod 설정

- [ ] 업로드 파일은 `/workspace/DreamCatcher.zip` 하나입니다.
- [ ] Private NVIDIA GPU Pod template을 사용했습니다.
- [ ] Image는 `runpod/comfyui:1.4.1-cuda12.8`이거나 live smoke가 끝난 private runtime prewarmed image입니다.
- [ ] Prewarmed image를 썼다면 `RUNPOD_TEMPLATE_PREWARMED_IMAGE`와 `DC_PREWARMED_IMAGE=runtime-v1`을 기록했습니다.
- [ ] GPU는 `RTX PRO 6000`, `96GB VRAM`입니다.
- [ ] Container Disk는 `80GB`입니다.
- [ ] Volume Disk는 `400GB`, Full Frontier + Qwen judge 사용 시 `500GB`입니다.
- [ ] Network Volume은 비활성화했습니다.
- [ ] Persistent model cache는 사용하지 않습니다.
- [ ] `HF_TOKEN`이 있고 gated license를 수락했습니다.
- [ ] `DC_MODEL_PROFILE=frontier`, `DC_SERVE_FRONTEND=1`, `DC_COMFY_PUBLIC=0`입니다.

## 2. Bootstrap

- [ ] `bash /workspace/DreamCatcher/runpod/bootstrap.sh --profile frontier`가 성공했습니다.
- [ ] bootstrap 로그에 placeholder workflow 경고가 없고, seed 검증이 실패를 무시하지 않았습니다.
- [ ] `bootstrap_summary.json`이 생성되었습니다.
- [ ] `runpod_model_bootstrap_contract.json`의 `model_profile`은 `frontier`입니다.
- [ ] `qwen_judge` 모델 세트가 bootstrap 계약에 포함되었습니다.

## 3. Health

- [ ] Studio가 `http://127.0.0.1:8000`에서 열립니다.
- [ ] `/health`가 응답합니다.
- [ ] `/api/rawprep/health`가 응답합니다.
- [ ] `/api/runpod/model-profiles`는 `frontier` 하나만 반환합니다.
- [ ] `/api/runpod/template-policy`가 이미지, 포트, 저장소 정책을 반환합니다.
- [ ] `/api/runpod/template-policy`가 prewarmed image 후보와 `runpod/prewarm/Dockerfile.runtime`을 반환합니다.
- [ ] `/api/runpod/bootstrap-session`이 Ephemeral Zip Pod 정책을 반환합니다.
- [ ] `/demo/remove-bg`, `/demo/variants`, `/demo/error`는 `404`입니다.
- [ ] ComfyUI `8188/system_stats`가 응답합니다.

## 4. Studio Smoke

- [ ] 첫 화면은 Studio 작업 화면입니다.
- [ ] 작업면 `원본`, `RAW`, `편집`, `검수`, `납품`, `운영`이 보입니다.
- [ ] 왼쪽 도구, 중앙 캔버스, 오른쪽 판단 패널, 하단 RunPod strip이 보입니다.
- [ ] ComfyUI는 사용자 기본 진입점이 아닙니다.
- [ ] 한글 UI 문자열이 깨지지 않습니다.

## 5. Frontier Smoke

- [ ] BiRefNet cutout workflow 계약이 로드됩니다.
- [ ] Qwen edit/generation 경로가 준비됩니다.
- [ ] FLUX.2 Dev/Klein 경로가 준비됩니다.
- [ ] FLUX.1 Fill 경로가 준비됩니다.
- [ ] Z-Image 또는 OmniGen2 상태가 준비 또는 명시적 gap으로 기록됩니다.
- [ ] export package가 `/workspace/DreamCatcher/outputs` 아래 생성됩니다.

## 6. RAW Smoke

- [ ] 단일 RAW 입력은 SingleRaw 경로로 진입합니다.
- [ ] 3장 RAW 입력이 end-to-end로 실행됩니다.
- [ ] Studio `RAW 결과 목표`에서 `진실 보존`과 `공격적 복원 후보`를 선택할 수 있습니다.
- [ ] 9장 RAW는 기본 Studio UX가 아니라 rawprep/API/benchmark 연구 경로임을 기록했습니다.
- [ ] TriRaw report에 `tri_raw_baseline_v1` 경로가 기록됩니다.
- [ ] `tri_raw_frontier_v1` evidence 계약이 기록됩니다.
- [ ] merged HDR, denoised result, confidence map, ghost map, alignment evidence가 남습니다.
- [ ] `truth_preserving` 기본 결과와 `aggressive_restore` 후보의 차이, hallucination risk를 기록했습니다.
- [ ] `aggressive_restore_candidate_path`, `requires_review=true`, `delivery_default=false`가 report에 남습니다.
- [ ] `tri_raw_frontier_eval_v1` 평가가 남습니다.

## 7. 품질 자동화

- [ ] `/api/studio/quality-automation/policy`가 `Qwen3.6-35B-A3B-FP8`와 `qwen_judge_signal_v2`를 반환합니다.
- [ ] `cloud_fallback_enabled=false`입니다.
- [ ] 필요 시 `bash runpod/start_qwen_judge.sh`로 local judge가 시작됩니다.
- [ ] 품질 assessment가 생성되고 `pass/suspicious/fail`이 기록됩니다.
- [ ] 품질 assessment에 `axis_scores`, `localized_issues`, `correction_plan`이 기록됩니다.
- [ ] 품질 assessment에 `judge_evidence_packet_v1`이 기록되고 작업 의도, metric, mask/RAW/workflow/선호/golden 근거가 확인됩니다.
- [ ] 품질 assessment에 `golden_calibration_v1`이 기록되고 calibrated verdict/confidence와 replay case가 확인됩니다.
- [ ] `suspicious`와 `fail`은 사람 승인 또는 재시도를 요구합니다.
- [ ] tuning proposal은 proposal-only로 남고 자동 반영되지 않습니다.

## 8. 회수와 종료

- [ ] 최종 이미지와 납품 패키지가 생성되었습니다.
- [ ] `/workspace/DreamCatcher/outputs`를 회수했습니다.
- [ ] 품질 판단, RAW evidence, bootstrap evidence를 필요한 만큼 회수했습니다.
- [ ] 실행 중인 작업이 없습니다.
- [ ] Pod를 stop했습니다.
- [ ] Pod를 terminate했습니다.
- [ ] 다음 세션은 새 Pod와 `DreamCatcher.zip`만으로 다시 시작할 수 있습니다.

## 9. 단계별 실사용 테스트 계획

### 9.1 로컬 산출물 준비

목표: RunPod에 올릴 `Product/DreamCatcher.zip`을 새로 생성합니다.

```powershell
cd C:\my_project\DreamCatcher
git pull origin main
git status --short
uv run --directory app\backend pytest
npm run typecheck --prefix app\frontend
npm run build --prefix app\frontend
python app\scripts\verify_seed_bundle.py --seed-root seed_bundle
uv run --project app\backend python runpod\preflight_release_bundle.py
```

보고:

```text
단계: 0 로컬 산출물
상태:
git status:
pytest:
typecheck:
build:
seed verify:
preflight:
DreamCatcher.zip 생성 위치:
```

### 9.2 Pod 생성

목표: RTX PRO 6000 기준 template과 저장소 정책을 확인합니다.

```text
GPU: RTX PRO 6000 96GB
Image: runpod/comfyui:1.4.1-cuda12.8
Container Disk: 80GB
Volume Disk: 500GB 권장, Qwen judge 포함
Network Volume: disabled
Ports: 8000/http, 8188/http, 22/tcp
Env:
HF_TOKEN=<secret>
DC_MODEL_PROFILE=frontier
DC_SERVE_FRONTEND=1
DC_COMFY_PUBLIC=0
```

보고:

```text
단계: 1 Pod 생성
상태:
GPU:
Image:
Disk:
Ports:
Env 설정 여부:
Pod 시작까지 걸린 시간:
```

### 9.3 Zip 업로드와 압축 해제

목표: `/workspace/DreamCatcher`가 정확히 생성되는지 확인합니다.

```bash
ls -lh /workspace/DreamCatcher.zip
cd /workspace
python3 - <<'PY'
from pathlib import Path
import zipfile

with zipfile.ZipFile(Path("/workspace/DreamCatcher.zip"), "r") as zf:
    zf.extractall("/workspace")
PY
ls -la /workspace/DreamCatcher
```

보고:

```text
단계: 2 Zip 업로드/해제
상태:
DreamCatcher.zip 크기:
압축 해제 결과:
실패 로그:
```

### 9.4 Frontier Bootstrap

목표: fresh Pod에서 Full Frontier bootstrap이 성공하는지 확인합니다.

```bash
cd /workspace/DreamCatcher
time bash runpod/bootstrap.sh --profile frontier
```

성공 후 확인:

```bash
ls -lh app/runtime
cat app/runtime/bootstrap_summary.json | head -80
cat app/runtime/runpod_model_bootstrap_contract.json | head -80
cat app/runtime/runpod_storage_contract.json | head -80
```

보고:

```text
단계: 3 Bootstrap
상태:
총 소요 시간:
실패한 다운로드:
생성된 runtime artifact:
bootstrap_summary 핵심:
model contract 핵심:
storage contract 핵심:
```

### 9.5 Health Check

목표: Studio, API, ComfyUI가 살아있는지 확인합니다.

```bash
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/api/rawprep/health
curl -s http://127.0.0.1:8000/api/runpod/model-profiles
curl -s http://127.0.0.1:8000/api/runpod/template-policy
curl -s http://127.0.0.1:8000/api/runpod/bootstrap-session
curl -s http://127.0.0.1:8188/system_stats
```

보고:

```text
단계: 4 Health
상태:
8000 /health:
rawprep health:
model-profiles:
template-policy:
bootstrap-session:
8188 system_stats:
```

### 9.6 Studio UI Smoke

목표: 실제 Studio 화면이 사용 가능한지 확인합니다.

브라우저에서 RunPod `8000` public URL을 열고 확인합니다. ComfyUI `8188`은 필요할 때만 엽니다.

보고:

```text
단계: 5 UI Smoke
상태:
스크린샷:
한글 깨짐:
겹침:
헷갈리는 문구:
첫 사용 흐름에서 막힌 지점:
```

### 9.7 기본 편집 Workflow Smoke

목표: 이미지 1장으로 입력, 편집, 검수, 납품 흐름을 확인합니다.

권장 순서:

1. JPG/PNG 1장 업로드
2. 입력 분석
3. `removeBg` 또는 `retouch` 실행
4. 결과를 작업 소스로 채택
5. `compare` 또는 `검수`로 이동
6. 납품 패키지 생성

보고:

```text
단계: 6 편집 Workflow
상태:
사용한 입력:
사용한 도구:
job 상태:
결과 파일 경로:
Comfy workflow 오류:
export package 경로:
```

### 9.8 RAW Smoke

목표: 단일 RAW, 3장 RAW 병합/디노이징/evidence, 공격적 복원 후보의 검수 가능성을 확인합니다.

보고:

```text
단계: 7 RAW Smoke
상태:
RAW 파일 수/카메라:
입력 경로: SingleRaw / TriRaw 3-frame / rawprep 9-frame 연구 경로
실행 시간:
추천 결과:
confidence/ghost/alignment artifact 경로:
fallback 여부:
truth_preserving 결과:
aggressive_restore 후보:
hallucination/detail reconstruction 의심:
눈으로 봤을 때 문제:
```

### 9.9 Qwen Judge Live Smoke

목표: local Qwen judge가 실제 판단하고 quality artifact를 남기는지 확인합니다.

```bash
cd /workspace/DreamCatcher
bash runpod/start_qwen_judge.sh
```

다른 터미널에서:

```bash
curl -s http://127.0.0.1:8000/api/studio/quality-automation/policy
find /workspace/DreamCatcher/outputs/_quality_automation -maxdepth 4 -type f | sort | tail -40
```

보고:

```text
단계: 8 Qwen Judge
상태:
Qwen 시작 로그:
VRAM 사용량:
quality policy 응답:
assessment artifact 경로:
verdict:
confidence:
golden calibrated verdict:
문제 태그:
재시도 지시:
```

### 9.10 결과 회수

목표: terminate 전에 산출물과 evidence를 회수합니다.

회수 대상:

- `/workspace/DreamCatcher/outputs`
- `/workspace/DreamCatcher/app/runtime/bootstrap_summary.json`
- `/workspace/DreamCatcher/app/runtime/runpod_model_bootstrap_contract.json`
- `/workspace/DreamCatcher/app/runtime/runpod_storage_contract.json`
- `/workspace/DreamCatcher/app/runtime/runpod_custom_node_contract.json`
- 품질 assessment, tuning proposal, RAW evidence, export package

보고:

```text
단계: 9 결과 회수
상태:
회수한 경로:
로컬/외부 저장 위치:
누락된 evidence:
다운로드 실패:
```

### 9.11 Stop / Terminate

목표: 비용 누수 없이 종료합니다.

순서:

1. 실행 중 job 없음 확인
2. outputs/evidence 회수 확인
3. Pod stop
4. Pod terminate
5. RunPod 콘솔에서 과금 리소스 잔존 여부 확인

보고:

```text
단계: 10 종료
상태:
outputs 회수 완료:
실행 중 job:
stop 시각:
terminate 시각:
남은 volume/network volume 여부:
```
