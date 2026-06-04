# DreamCatcher User Manual

최종 갱신: 2026-05-12

## 1. 한 줄 요약

DreamCatcher는 개인용 프로 사진 편집 Studio입니다. 사용자는 ComfyUI가 아니라 Studio 화면에서 `원본 -> RAW -> 편집 -> 검수 -> 납품 -> 운영` 작업면을 따라 RAW 준비, 편집, 품질 검사, 출력, Pod 종료까지 처리합니다.

## 2. 접속

RunPod:

- Studio: `http://<runpod-8000-url>`
- ComfyUI 관리자: `8188`, 필요할 때만 공개

로컬:

- Backend: `http://127.0.0.1:8000`
- Frontend: `http://127.0.0.1:4173`

## 3. 작업면

| 작업면 | 하는 일 |
| --- | --- |
| `원본` | RAW/JPG/TIFF/PNG/WebP/HEIC 추가, 입력 분석, 시작 경로 선택 |
| `RAW` | SingleRaw, TriRaw, 병합/디노이즈, confidence/ghost/alignment 근거 확인 |
| `편집` | 배경 제거, 배경 생성, 오브젝트 편집, 화면 확장, 조명, 리터치, 품질 개선 |
| `검수` | Qwen 판단, 전용 지표, 마스크/RAW 근거, 비교, 재시도 지시, 사람 승인 |
| `납품` | 최종 이미지 저장, 납품 preset, proofing sheet, session package 생성 |
| `운영` | RunPod 상태, 모델/bootstrap 상태, outputs 회수, stop/terminate 확인 |

일반 JPG/TIFF 작업은 `RAW`를 건너뛰고 바로 `편집`으로 갈 수 있습니다.
작업면 탭은 각 화면의 현재 상태를 함께 보여줍니다. 처음에는 `원본`에서
`원본 -> 분석 -> 시작` 흐름을 확인하고 다음 작업을 누릅니다.

## 4. 실사용 테스트와의 연결

RunPod 실사용 smoke는 `PROJECT_FOUNDATION/RUNPOD_VALIDATION_CHECKLIST.md`의 단계별 계획을 따릅니다. 이 User Manual은 그 테스트 중 Studio 안에서 실제로 조작하는 흐름을 설명합니다.

대응 관계:

- 테스트 `5 UI Smoke`: 이 문서의 `접속`, `작업면`
- 테스트 `6 편집 Workflow`: 이 문서의 `기본 작업 순서`, `품질 검사`, `출력과 종료`
- 테스트 `7 RAW Smoke`: 이 문서의 `RAW 작업`
- 테스트 `8 Qwen Judge`: 이 문서의 `품질 검사`
- 테스트 `9 결과 회수`, `10 종료`: 이 문서의 `출력과 종료`

## 5. 기본 작업 순서

1. `원본`에서 파일을 추가합니다.
2. `입력 분석`을 실행하고 `원본 -> 분석 -> 시작` 흐름의 다음 작업을 확인합니다.
3. RAW 브라켓이면 `RAW 결과 목표`를 고르고 `RAW`에서 TriRaw를 실행합니다.
4. 사용할 작업 소스를 채택합니다.
5. `편집`에서 필요한 도구를 고르고 결과를 생성합니다.
6. `검수`에서 Qwen 판단, metric/checker, 비교 화면을 확인합니다.
7. 좋은 결과를 작업 소스로 채택하거나 재시도합니다.
8. `납품`에서 최종 이미지와 패키지를 저장합니다.
9. `운영`에서 `/workspace/DreamCatcher/outputs` 회수 후 Pod를 stop/terminate합니다.

## 6. RAW 작업

RAW 입력은 현재 Studio에서 두 경로가 공식입니다.

- 단일 RAW: `SingleRaw`
- 3장 RAW 브라켓: `TriRaw`

9장 RAW burst/HDR은 rawprep engine 계약과 연구 경로에는 열려 있지만, 아직 Studio 기본 업로드 흐름의 공식 작업면은 아닙니다. 9장 테스트는 RunPod smoke나 benchmark/API 경로에서 별도로 검증합니다.

확인할 항목:

- 기준 프레임과 병합 결과
- denoise 결과
- confidence map
- ghost map
- alignment evidence
- fallback 여부

현재 안정 경로는 `tri_raw_baseline_v1`입니다. `tri_raw_frontier_v1`은 더 많은 진단 근거와 연구 어댑터 연결을 위한 계약입니다.

RAW 결과 목표:

- `진실 보존`: 기본값입니다. ghost/noise를 줄이되 없는 질감은 만들지 않습니다.
- `공격적 복원 후보`: 더 강한 denoise/deblur/디테일 복원 후보를 별도로 만듭니다. 결과 스트립에는 `공격적 복원 후보`와 `검수 필요` 표시가 붙습니다.

공격적 복원 후보는 최종 결과로 자동 승격되지 않습니다. 더 선명해 보여도 가짜 디테일이나 경계 이동 위험이 있으므로 Qwen 검수, metric/golden 보정, 사람 승인 후에만 채택합니다.

## 7. 품질 검사

DreamCatcher는 결과를 채택하기 전에 품질 판단을 남깁니다.

- 판단 모델: `Qwen3.6-35B-A3B-FP8`
- 판단 스키마: `qwen_judge_signal_v2`
- 판단 입력: `judge_evidence_packet_v1`
- 점수 보정: `golden_calibration_v1`
- 보조 검사: 노출, 색, 선명도, 노이즈, 마스크, RAW 진단
- 판정: `pass`, `suspicious`, `fail`
- Cloud fallback: 사용하지 않음

Qwen 판단은 아래 내용을 함께 남깁니다.

- 의도 일치, 기술 품질, 심미 품질, 피사체 보존, 마스크 경계, 색 자연스러움 점수
- 문제가 보이는 영역과 실패 유형
- 노출, 대비, 암부, 하이라이트, 색온도, 틴트, 채도, 노이즈, 편집 강도 보정 제안

Qwen은 결과 이미지만 보지 않습니다. Studio는 작업 의도, before/after 지표, 마스크 근거, RAW confidence/ghost/alignment 근거, workflow 정보, 사용자 선호 기록, golden 기준을 함께 묶어 판단에 보냅니다.

처리 기준:

- `pass`: 채택 가능
- `suspicious`: 사람 확인 필요
- `fail`: 실패 태그와 재시도 지시 생성

Qwen 점수는 golden 기준으로 다시 보정됩니다. 코드, 프롬프트, preset, workflow, 지표 변경은 자동 적용하지 않습니다. 제안만 만들고, 사람 승인과 golden session 회귀 검증 후 반영합니다.

## 8. 출력과 종료

최종 종료 전 체크:

1. 최종 이미지와 납품 패키지를 저장합니다.
2. `/workspace/DreamCatcher/outputs`를 다운로드하거나 외부 저장소로 옮깁니다.
3. 필요하면 `bootstrap_summary.json`, RAW evidence, 품질 판단, tuning proposal을 함께 보관합니다.
4. 실행 중인 작업이 없는지 확인합니다.
5. Pod를 stop합니다.
6. Pod를 terminate합니다.

다음 세션은 새 Pod와 `DreamCatcher.zip`으로 다시 bootstrap합니다.
