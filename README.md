# DreamCatcher

DreamCatcher는 개인용 프로 사진 편집 Studio입니다. RAW 준비, 병합/디노이즈, 배경 제거/생성, 오브젝트 편집, 품질 검사, 납품 패키징을 하나의 작업 흐름으로 묶습니다.

이 저장소는 공개 가능한 소스와 제품 문서를 담은 public repo입니다. 실제 개발 history와 운영용 비공개 자료는 `DreamCatcher-private`에서 관리합니다.

## 프로젝트 한 줄 요약

ComfyUI를 직접 노출하는 대신, 모델 준비 상태와 워크플로우 검증, 품질 evidence, RunPod 납품 패키징까지 Studio UI에서 통제하는 사진 편집 도구입니다.

## 핵심 기능

- RAW 입력 준비와 seed bundle 검증
- ComfyUI 기반 이미지 편집 workflow orchestration
- 배경 제거, 배경 생성, 오브젝트 편집, 품질 검사 흐름
- RunPod ephemeral zip pod 기준의 release bundle 생성
- 모델 readiness, storage contract, custom node contract 검증
- 사용자 납품용 `Product/` 문서와 빌드 매뉴얼

## 기술 스택

| 영역 | 기술 |
| --- | --- |
| Frontend | React, Vite, TypeScript, Zustand, React Query |
| Backend | FastAPI, Python, uv |
| Image workflow | ComfyUI 연동, seed bundle, workflow contract |
| Runtime | RunPod GPU Pod, CUDA 기반 ComfyUI image |
| 품질 관리 | pytest, typecheck, release preflight |

## 저장소 구조

```text
DreamCatcher
├── app/backend             # FastAPI orchestration, tests, runtime contracts
├── app/frontend            # React Studio UI
├── Product                 # 사용자 빌드/실행 문서
├── PROJECT_FOUNDATION      # 제품/운영 기준 문서
├── runpod                  # RunPod bootstrap, preflight, release bundle 도구
└── seed_bundle             # 공개 가능한 seed/workflow 기준 자료
```

## 실행과 검증

```powershell
uv run --directory app\backend pytest
npm run typecheck --prefix app\frontend
npm run build --prefix app\frontend
python app\scripts\verify_seed_bundle.py --seed-root seed_bundle
uv run --project app\backend python runpod\preflight_release_bundle.py
```

## 공개/비공개 경계

공개 repo에는 live token, RunPod key, 모델 provider credential, 생성 output, 다운로드된 모델 weight, 로컬 runtime state를 넣지 않습니다. 운영 secret과 전체 개발 history는 private repo와 secret manager에서 관리합니다.
