# 시장별 체크리스트 크로스워크

치과 X-ray / SW 제품의 시장별 안전·성능 요건(EU GSPR 기준 허브)을 비교하는 정적 웹앱.
**참고용 초안**이며 제출 서류에 그대로 사용하지 않습니다. 국문은 AI 번역 초안(검토 필요).

## 사용
- `index.html` 을 브라우저에서 열면 됩니다 (서버 불필요, `file://` 가능). SharePoint/인트라넷에는 폴더째 올리면 됩니다.
- 탭: **비교**(체크리스트 2개 선택, 영/국 병기, 대응·갭 표시) / **업데이트 현황** / **안내·토픽**

## 데이터 수정
1. `data/checklists/{EU,CA,AU,HK,ASEAN,BR}.json`, `data/topics.json`, `data/sources.json`, `data/changelog.json` 을 편집
   - 토픽은 `"p:토픽ID"`(primary) / `"s:토픽ID"`(secondary) 형식
   - `verification`: `official`(원문 확인) / `handoff`(사전 조사) / `memory`(기억 기반, 대조 필요) / `unverified`(미검증)
2. 번들 재생성: `py -3 scripts/build_bundle.py` (→ `data/bundle.js`; 직접 수정 금지)

## 월간 점검
- `py -3 scripts/check_updates.py [--dry-run]` — 출처 조회, 변경 시 `changelog.json` 기록, `reports/latest.md` 작성, 번들 재생성
- `.github/workflows/monthly-check.yml` — 매월 1일 실행, 데이터 커밋 + 요약 Issue 생성
- 차단/접근 불가 출처는 우회하지 않고 수동 확인 목록으로 분리됩니다.
- `versionFields` 정규식은 첫 실행 결과(`pattern-miss` 여부)로 검증하세요.

## 참고
- IMDRF N47(FINAL:2018)에는 EU GSPR 대응표가 없습니다(부록 A=표준 활용, 부록 B=가이던스). ANVISA RDC 848의 구조는 N47 5.1–5.13 / 6.1–6.5와 같은 순서이며, GSPR↔N47 대응은 이 도구의 토픽 매핑(초안)이 대신합니다.
- 브라질(BR)은 두 층으로 구성: ① Cap. 00–07 = ANVISA 등록 서류 체크리스트 양식(컨설턴트 작성, Risk Class III용)의 요구 정보를 하위 요건 단위로 정리(handoff 수준, 제품별 기재 내용 제외) ② RDC 848/2024 필수 원칙(조항별, 공식 원문 확인).
- 홍콩 MD-CCL 양식은 N47 번호 체계가 아니라 clause 1–17 구조입니다(빈 양식만 사용, 제품별 기재 내용은 도구에 넣지 않음).
- 공식 문서가 PDF로만 확인될 때는 격리 venv에 `pypdf`를 설치해 텍스트를 추출해 읽었습니다(프로젝트 의존성 아님).

## 비교 탭의 섹션 매칭
A로 고른 체크리스트의 각 섹션 옆에 B에서 내용이 가까운 섹션을 개수 제한 없이 연결합니다(1위 점수의 70% 이상, `MATCH_REL`). 한 행 안에서 직접 대응을 먼저, 그 아래에 부분 대응을 보여주며, 직접은 3개(`CORE_N`)·부분은 2개(`CORE_P`)만 먼저 펼치고 나머지는 "더 보기"로 접습니다.
- 내부적으로 섹션마다 공통 토픽(`topics`)이 붙어 있고, 같은 토픽을 가진 B 섹션 중 영문 문구 유사도가 높은 순서로 고릅니다.
- 양쪽 primary 토픽이 겹치면 "직접 대응", 보조만 겹치면 "부분 대응", 겹치는 토픽이 없으면 "대응 없음".
- B에서 어느 A 섹션과도 연결되지 않은 섹션은 화면 맨 아래 "B에만 있는 섹션"에 모읍니다.
- 연결은 참고용 초안이며 RA 검토가 필요합니다.
