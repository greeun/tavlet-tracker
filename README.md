# tavlet-tracker

Claude Code 세션에서 **실제로 수행한 개발 작업**을 [tavlet](https://tavlet.io) 피드백 보드에 등록·추적하는 스킬.

어느 레포에서 작업하든, 세션이 끝날 때 `/tvl` 한 번으로 post 등록 → task 분해 → 증거 기반 다이제스트 댓글 → 상태 전이까지 보드에 반영한다.

## 무엇을 하는가

- **post 등록** — 기존 post 중복 탐색 후 신규 등록
- **task 분해·상태 갱신** — 내부 체크리스트 생성, TODO/DOING/DONE 전이
- **세션 다이제스트 댓글** — 파일 경로·커밋 해시·명령 출력 등 세션의 실제 증거로 작성
- **post 상태 전이** — 보드 컬럼(칸반) 배치 포함
- **분류·중복 제안** — 카테고리·태그 제안, 중복 후보 지목
- **릴리스 초안** — 완료 post를 모아 체인지로그 초안 패키지 등록

접근 경로는 MCP 서버가 노출하는 **board 도구 14종**뿐이다. REST를 직접 호출하거나 보드에 접근하는 우회 스크립트를 만들지 않는다 — 그것은 승인 게이트를 우회하는 두 번째 쓰기 경로다. (보드에 접근하지 않고 초안 텍스트만 읽는 검증기 `scripts/validate_drafts.py` 는 예외다 — 부작용을 낼 수 없다.)

## 안전 장치

모든 쓰기는 프로덕션 `tavlet.io`에 대한 **되돌리기 어려운 부작용**이고, 대상 보드 중 일부는 **외부 독자가 읽는 공개 면**이다. 그래서 이 스킬의 하네스는 "더 나은 글"이 아니라 **"등록해도 되는 글"** 을 만든다.

- **승인 게이트** — 모든 쓰기는 정확한 인자 미리보기 + 사용자 명시 승인을 거친다
- **결정론 검증기** (`scripts/validate_drafts.py`) — 초안의 도구 계약·enum·길이 상한·시크릿 누출·증거 좌표를 기계적으로 판정한다. 읽기 전용이며 보드에 접근하지 않는다
- **Planner → Generator → Evaluator 하네스** — 등록 전 초안을 적대적으로 심사한다. 판단이 필요한 축만 남긴다
  - 증거 구체성: 파일 경로·커밋 해시·명령 출력이 실재하는가
  - 세션 사실성: 실제로 하지 않은 일을 쓰지 않았는가
  - 중복 정찰 재현: 기존 post 갱신이어야 할 것을 신규 등록하려 하지 않는가
  - 비밀·개인정보 스크럽: PAT·`.env` 값·API 키·개인 이메일·홈 절대경로가 남아 있지 않은가
  - 공개면 경고: 대상 보드가 공개면이면 미공개 내부 정보 잔존 여부를 추가 심사
- **테넌트 확정** — 매 실행 `board_list_boards()` 반환에 대상 boardId 가 실재함을 확인한다. 대상 보드를 조용히 정하는 경로는 쓰지 않는다

## 설치

### 1. MCP 서버 등록

tavlet.io 가입 후 콘솔에서 PAT(개인 액세스 토큰)를 발급받는다. 대상 보드에 **WRITE grant**가 포함되어야 한다.

```bash
export TAVLET_BOARD_TOKEN_TAVLET_IO="tvl_..."

claude mcp add tavlet \
  --transport http \
  --scope local \
  --header "Authorization: Bearer $TAVLET_BOARD_TOKEN_TAVLET_IO" \
  https://tavlet.io/api/mcp
```

로컬에 설치하거나 클론할 것은 없다 — 서버는 tavlet.io 가 운영한다.

> **멀티테넌트 주의:** org마다 PAT가 다르다. MCP 등록은 **프로젝트(= org/보드) 단위로 분리**한다. 하나의 등록을 여러 org에 재사용하면 테넌트 오등록의 출발점이 된다.

### 2. 스킬 배포

```bash
git clone https://github.com/greeun/tavlet-tracker.git
cd tavlet-tracker

ln -s "$(pwd)" ~/.claude/skills/tavlet-tracker
ln -s "$(pwd)/commands/tvl.md" ~/.claude/commands/tvl.md
```

복사가 아니라 **심링크**를 둔다 — 복사본은 정본과 조용히 갈라진다. 갱신은 `git pull` 이면 된다.

### 3. 확인

세션을 재시작하고 `board_list_boards` 도구가 존재하는지, 반환 목록에 대상 boardId 가 있는지 확인한다. 자세한 스모크 테스트와 진단 분기는 [`references/mcp-setup.md`](references/mcp-setup.md) §4–5.

## 사용

```
/tvl
```

또는 자연어로: "tavlet 등록", "보드에 올려", "작업 기록", "세션 결과 보드 반영", "릴리스 초안".

## 문서

| 파일 | 내용 |
|---|---|
| [`SKILL.md`](SKILL.md) | 에이전트 동작 정본 — 게이트·하네스·경로 규약 |
| [`references/mcp-setup.md`](references/mcp-setup.md) | MCP 배선, `.tavlet.json` 스키마, 진단 분기 |
| [`references/board-tool-contract.md`](references/board-tool-contract.md) | board 도구 14종 계약 |
| [`references/rubric.md`](references/rubric.md) | Evaluator 채점 루브릭 |
| [`scripts/validate_drafts.py`](scripts/validate_drafts.py) | 초안 결정론 검증기 (읽기 전용) |

`SKILL.md` 가 에이전트 동작의 단일 정본이다. 이 README는 사람이 읽는 문서이며 런타임에 필요하지 않다.

## 요구사항

- Claude Code
- tavlet.io 계정 + 대상 org 멤버십 + PAT
