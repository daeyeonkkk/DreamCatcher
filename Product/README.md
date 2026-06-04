# DreamCatcher Product

최종 갱신: 2026-05-12

이 폴더는 DreamCatcher를 실제로 사용하고 RunPod에 올릴 때 보는 납품물 묶음입니다.
개발 판단 기준은 `PROJECT_FOUNDATION/README.md` 하나만 봅니다.

작업 전에는 `PROJECT_FOUNDATION/README.md`를 확인하고, 작업 후에는 이 폴더의
납품 문서가 바뀌어야 하는지 반드시 검토합니다. 작업이 끝나면 검증 후
커밋합니다.

## 포함 문서

- `USER_MANUAL.md`: Studio 사용 흐름
- `BUILD_MANUAL.md`: 로컬 빌드, `DreamCatcher.zip` 생성, RunPod bootstrap

실제 RunPod smoke 체크리스트와 단계별 리포트 양식은
`PROJECT_FOUNDATION/RUNPOD_VALIDATION_CHECKLIST.md`를 봅니다.

## 새 환경에서 시작

`git pull` 또는 fresh clone 뒤에는 아래만 보면 됩니다.

1. 개발 방향과 원칙: `PROJECT_FOUNDATION/README.md`
2. 사용 방법: `Product/USER_MANUAL.md`
3. 빌드와 RunPod bootstrap: `Product/BUILD_MANUAL.md`
4. RunPod 검증: `PROJECT_FOUNDATION/RUNPOD_VALIDATION_CHECKLIST.md`

`Product/DreamCatcher.zip`은 git에 들어가지 않는 생성물입니다. 새 환경에서는
`Product/BUILD_MANUAL.md`의 검증 명령을 실행해서 다시 만듭니다.

## 생성 결과물

- `Product/DreamCatcher.zip`
  - `runpod/preflight_release_bundle.py`가 기본으로 생성하는 공식 업로드 파일
  - git에는 커밋하지 않습니다.
  - RunPod에는 `/workspace/DreamCatcher.zip`로 업로드합니다.

## 현재 고정 정책

- GPU: `RTX PRO 6000`, `96GB VRAM`
- Image: `runpod/comfyui:1.4.1-cuda12.8`
- Optional prewarmed image: `runpod/prewarm/Dockerfile.runtime`로 만든 private runtime image
- Model profile: `frontier`
- Container Disk: `80GB`
- Volume Disk: `400GB`, Full Frontier + Qwen judge 사용 시 `500GB`
- Network Volume: 기본 비활성화
- Persistent model cache: 사용하지 않음
- Cold-start: Full Frontier + Qwen judge fresh bootstrap은 보통 `60-150 min`
- Prewarm 범위: runtime cache만, 모델 weight와 output은 굽지 않음
- RAW result goal: 기본 `truth_preserving`, 선택 `aggressive_restore` 후보
- Quality automation: `Qwen + judge_evidence_packet_v1 + golden_calibration_v1 + human approval`
- Mock/demo API: runtime과 zip에 포함하지 않음. Placeholder workflow는 검증 실패로 처리
- Pod 종료: outputs 회수 후 stop, terminate
