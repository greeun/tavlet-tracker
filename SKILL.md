---
name: tavlet-tracker
description: 임의의 Claude Code 세션(어느 레포에서든)에서 수행한 작업을 tavlet 피드백 보드에 MCP board 서버 도구 14종으로 등록·추적한다 — 기존 post 중복 탐색 → post 등록 → task 분해·상태 갱신 → 증거 기반 세션 다이제스트 댓글 → post 상태 전이 → 분류/중복 제안 → 릴리스 초안까지 전체 라이프사이클. 모든 쓰기는 정확한 인자 미리보기 + 사용자 명시 승인 게이트를 거치고, Planner→Generator→Evaluator 하네스가 등록 전 초안의 증거 구체성(파일 경로·커밋 해시·명령 출력)과 세션 사실성(환각 금지)을 적대적으로 심사한다. 멀티테넌트이므로 MCP 등록은 프로젝트 단위로 분리한다. 트리거 — KO "tavlet 등록", "보드에 올려", "작업 기록", "tvl", "타블렛 보드", "보드에 기록", "post 등록", "task 상태 갱신", "세션 결과 보드 반영", "릴리스 초안". EN "tavlet", "log work to tavlet", "track work on tavlet board", "register post on tavlet board".
version: 1.1.0
---

# tavlet-tracker

이 세션에서 **실제로 수행한 개발 작업**을 tavlet 피드백 보드에 등록·추적한다. 접근 경로는 MCP 서버가 노출하는 **도구 14종**뿐이다(정규 경로는 원격 `https://tavlet.io/api/mcp`, 등록은 `references/mcp-setup.md`). REST를 직접 호출하거나 별도 스크립트를 만들지 않는다 — 그것은 승인 게이트를 우회하는 두 번째 쓰기 경로다.

모든 쓰기는 프로덕션 `tavlet.io`에 대한 **되돌리기 어려운 부작용**이고, 대상 보드 중 일부는 **외부 독자가 읽는 공개 면**이다. 그래서 이 스킬의 하네스는 "더 나은 글"이 아니라 **"등록해도 되는 글"** 을 만든다.

## 이 스킬의 핵심 원칙

- **기계가 거르는 것과 사람이 정하는 것은 다르다.** Planner→Generator→Evaluator 하네스는 *근거 없는 문장*을 거른다 — 좌표 없는 결과 주장, 세션에서 관측되지 않은 사실, 도구 계약 위반, 시크릿 잔존. 반면 **"이 등록이 애초에 옳은 판단인가"** 는 조직 맥락·공개 정책·타이밍에 달려 있고 **사람만 결정할 수 있다.**
- **따라서 사용자 승인 게이트(G5)가 이 도메인의 human checkpoint다.** 다른 하네스 스킬에서 "사람이 직접 보고 들어야 하는 감각 한계"가 차지하는 자리를, 여기서는 **부작용 한계**가 차지한다.
- **이 게이트는 영구다.** 모델이 좋아져서 사라지는 종류가 아니다 — 컨텍스트 한계 문제가 아니라 **외부 시스템에 대한 부작용 권한** 문제이기 때문이다.
- **증거 없는 기록은 기록이 아니라 오염이다.** 3개월 뒤 그 문장으로 아무것도 검증할 수 없다면, 보드에 남길 이유도 없다.
- **실패와 미검증을 지우지 않는다.** 지운 실패는 다음 사람의 시간이다.

## 범위 — 언제 켜고 언제 끄는가

**켠다:** 이 세션에서 한 작업을 tavlet 보드에 반영해야 할 때. 즉 **쓰기가 계획될 때만.**

**끈다(활성화하지 않는다):**
- Linear · Jira · GitHub Issues 등 **다른 트래커** 기록 요청 → 해당 스킬의 영역.
- tavlet **앱 코드 구현·수정** 요청 → tavlet 레포 세션 + `tavlet-board-work`(S3)의 영역.
- 보드 **UI·디자인** 작업, tavlet 배포·릴리스 **발행**(이 스킬은 초안 생성까지만).
- 보드 **읽기 전용 질의**("이 post 뭐야?") → 읽기 도구를 직접 쓰면 되고 하네스가 필요 없다.

## 기존 tavlet 레포 스킬과의 경계

tavlet 레포 안에는 세션 전용 파이프라인 스킬이 이미 있다: `tavlet-board-submit`(S0) · `-intake`(S1) · `-analyze`(S2) · `-work`(S3) · `-result`(S4) · `-review` · `tavlet-release-draft`, 진입점 `/tav`.

| | tavlet 레포 내부 스킬 (S0~S4) | tavlet-tracker (이 스킬) |
|---|---|---|
| 실행 위치 | tavlet 레포 세션에서만 | **레포 밖 임의 세션** |
| 대상 작업 | 보드 post에서 출발해 tavlet을 구현 | **다른 레포에서 이미 한 작업**을 보드에 반영 |
| 구조 | 얇은 스킬 6종의 순차 파이프라인 | 단일 스킬 + Planner/Generator/Evaluator 하네스 |
| 품질 보증 | 각 스킬의 미리보기·승인 게이트 | 승인 게이트 + **등록 전 증거·사실성 적대 심사** |

> ⚠️ **위 비교표의 왼쪽 열(S0~S4 파이프라인)은 더 이상 존재하지 않는다.** tavlet 레포의
> `agent/skills/tavlet-board-*` 와 `agent/commands/tav.md` 는 2026-08-22 커밋 `ff3fa1f`
> ("tavlet 보드 스킬·커맨드·MCP 등록 제거")에서 삭제됐고, tavlet `CLAUDE.md` 는 보드 등록을
> **이 스킬 경로로 대체**한다고 기록한다. 표는 두 경로가 공존하던 시기의 이력으로 남긴다.

**경계 규칙(게이트 G2) — 폐기됨:**
- 원래 판정은 "레포 루트에 `agent/mcp/board/server.ts` **와** `agent/skills/tavlet-board-submit/SKILL.md` 가 **둘 다** 존재"였다. 후자가 `ff3fa1f` 에서 삭제되어 **이 조건은 영구히 거짓**이고, 핸드오프 대상(`/tav`)도 함께 사라졌다.
- 따라서 tavlet 레포에서 실행하더라도 **핸드오프를 제안하지 않는다** — 이 스킬이 유일한 보드 등록 경로다.
- 게이트 번호 G2는 하위 참조가 깨지지 않도록 **비워 둔 채 유지**한다. 새 게이트에 재사용하지 않는다.
- 커밋 트레일러 `[tv:<taskId>]` 는 두 경로 공존을 위한 규약이었다. 현재 tavlet `CLAUDE.md` 에 기재가 없고 최근 커밋에도 쓰이지 않으므로 **요구하지 않는다.**

## 역할 분리

Planner · Generator · Evaluator는 **각각 별도의 `Agent` 호출**이며 **파일로만 통신한다.** 서로의 추론 과정을 보지 않는다.

| 역할 | 프롬프트 | 입력 | 산출 | 도구 권한 |
|---|---|---|---|---|
| **Planner** | `references/planner-prompt.md` | 세션 사실 목록 + 정찰 결과 | `spec.md` — 보드 변경 계획 | 읽기 7종 + 로컬 파일·`git` |
| **Generator** | `references/generator-prompt.md` | `spec.md` (+ 재시도 시 `critique_v<n-1>.md` · 승인된 PIVOT 이면 `design_memo_v<n-1>.md` · 리셋 이어받기면 그 라운드의 `handoff_v<n>*.md` **전부**) | `drafts_v<n>.md` + `generator_report_v<n>.md` | 읽기 7종 + 로컬 파일·`git`. **쓰기 7종 호출 금지** |
| **Evaluator** | `references/evaluator-prompt.md` | `spec.md` + `drafts_v<n>.md` + `generator_report_v<n>.md` (+ 2라운드부터 `critique_v<n-1>.md` · `drafts_v<n-1>.md`) | `critique_v<n>.md` (PASS/FAIL) | 읽기 7종 + 로컬 파일·`git`. **쓰기 7종 호출 금지** |

**쓰기 7종을 실제로 호출하는 것은 오케스트레이터(이 스킬을 실행하는 메인 세션)뿐이며, 사용자 승인 이후에만이다.**

세 프롬프트는 각각 자기완결이다. 단, 셋 모두 `references/board-tool-contract.md`를 읽는다 — 14종 계약을 세 곳에 복사하면 갈라진다. 표의 상대 경로는 **다음 절의 `SKILL_ROOT` 기준**이며, 디스패치 시점에 절대 경로로 치환해 넘긴다.

## 경로 규약 — `SKILL_ROOT` · `RUN_DIR`

세 역할은 **사전 맥락이 0**인 별도 서브에이전트다. cwd는 이 스킬과 무관한 임의의 레포이고, 스킬 정본은 심링크(`~/.claude/skills/tavlet-tracker`)를 통해 열린다. **따라서 상대 경로 `references/…` 는 서브에이전트에게 해소되지 않는다.** 디스패치 전에 두 경로를 확정한다.

**`SKILL_ROOT`** — 이 `SKILL.md`가 있는 디렉터리의 절대 경로. 설치 위치는 사람마다 다르므로 **매 실행 해소한다:**

```bash
ls -l ~/.claude/skills/tavlet-tracker
```

심링크면 `->` 뒤가 `SKILL_ROOT`다(정본은 https://github.com/greeun/tavlet-tracker 클론 경로). 심링크 경로를 그대로 넘겨도 되지만 **한 실행 안에서는 한 형태로 통일한다.**

**`RUN_DIR`** — 이번 실행의 런 디렉터리. 실행마다 새로 만든다:

```
<세션 스크래치패드>/tavlet-tracker/<YYYYMMDD-HHMMSS>/
```

스크래치패드 경로를 모르면 `mktemp -d` 로 만들고 그 절대 경로를 쓴다. **스킬 폴더 안에는 실행 산출물을 만들지 않는다.**

**라운드 파일을 덮어쓰지 않는다.** 라운드 `n`의 산출물에는 접미사 `_v<n>`을 붙여 `RUN_DIR` 바로 아래 둔다. 특히 `critique_v<n>.md`는 **절대 덮어쓰지 않는다** — 라운드 간 비교(최선 라운드 선택, Iteration Quality Note)가 이 파일들의 공존에 의존한다.

**접미사가 붙지 않는 파일 2종.** `spec.md`(Planner. 계획은 런당 1회)와 `execution_state.md`(오케스트레이터. 실행은 PASS 이후 런당 1회)는 **라운드 차원이 없으므로** `_v<n>`을 붙이지 않는다. 라운드 번호가 없다는 것이 "다른 파일로 갈아치워도 된다"는 뜻은 아니다 — 둘 다 런당 1개이며 제자리에서 갱신한다.

**같은 라운드에서 리셋이 두 번 나면** 그 라운드의 handoff 를 덮어쓰지 않고 접미 문자를 붙인다 — `handoff_v<n>.md` → `handoff_v<n>b.md` → `handoff_v<n>c.md`. 이어받는 세션은 그 라운드의 handoff 파일을 **전부 이 순서대로** 읽는다.

### 디스패치 주입 블록 — 7·8·9단계에서 각 역할 프롬프트 **앞에** 붙인다

```text
[경로 — 오케스트레이터가 확정해 주입한 값이 정본이다. 추측하거나 상대 경로로 바꾸지 않는다]
SKILL_ROOT = <절대 경로>
RUN_DIR    = <절대 경로>

읽을 파일 (전부 절대 경로로 전개해 나열한다):
- {SKILL_ROOT}/references/board-tool-contract.md      (Planner · Generator · Evaluator)
- {SKILL_ROOT}/references/rubric.md                   (Generator · Evaluator)
- {SKILL_ROOT}/references/evaluator-calibration.md    (Evaluator)
- {RUN_DIR}/spec.md                                   (Generator · Evaluator)
- {RUN_DIR}/drafts_v<n>.md                            (Evaluator)
- {RUN_DIR}/generator_report_v<n>.md                  (Evaluator)
- {RUN_DIR}/critique_v<n-1>.md     (있으면)  (재시도 Generator = Strategic Decision 의 근거 · Evaluator = Iteration Quality Note 의 비교 근거)
- {RUN_DIR}/drafts_v<n-1>.md       (있으면)  (Evaluator — 직전 라운드 초안. Iteration Quality Note 에서 실제로 열어 비교한다)
- {RUN_DIR}/design_memo_v<n-1>.md  (있으면)  (Generator — 직전 라운드가 제안하고 오케스트레이터가 승인한 PIVOT. 이 파일 없이는 방향을 바꾸지 않는다)
- {RUN_DIR}/handoff_v<n>.md        (있으면)  (컨텍스트 리셋 후 라운드 n 을 이어받는 새 Generator — 초안 진행 상태. 다른 무엇보다 먼저 읽는다)
- {RUN_DIR}/handoff_v<n>b.md       (있으면)  (같은 라운드의 두 번째 리셋. c·d 까지 존재하는 것을 전부 이 순서대로 열거한다 — 뒤엣것이 앞엣것을 대체하지 않는다)

「(있으면)」이 붙은 행은 전부 조건부 입력이다. 그 상황(재시도 · 승인된 PIVOT · 컨텍스트 리셋)이 아니면
파일 자체가 없으므로 그 줄을 목록에서 뺀다. 목록에 남긴 줄은 "이 파일은 존재한다"는 선언이다.

쓸 파일 (전부 절대 경로):
- Planner    → {RUN_DIR}/spec.md
- Generator  → {RUN_DIR}/drafts_v<n>.md · {RUN_DIR}/generator_report_v<n>.md
               (필요 시 {RUN_DIR}/design_memo_v<n>.md · {RUN_DIR}/handoff_v<n>.md.
                이미 handoff_v<n>.md 가 있으면 …b.md, 그다음은 …c.md — 덮어쓰지 않는다)
- Evaluator  → {RUN_DIR}/critique_v<n>.md

{RUN_DIR}/execution_state.md 는 이 목록에 없다. 12단계 실행 상태의 정본이며 **오케스트레이터만**
쓴다 — 세 역할은 쓰기 도구를 호출하지 않으므로 적을 내용이 없다. 읽지도 쓰지도 지어내지도 않는다.
```

**`BLOCKED` 규약.** 세 프롬프트 전부 최상단에 같은 하드룰을 싣는다 — 위 목록의 파일을 **열지 못하면 기억으로 진행하지 않고** `BLOCKED: <열지 못한 절대 경로>` 를 출력하고 멈춘다. **조건부 파일에는 이렇게 적용한다** — 주입 목록에 애초에 올리지 않아 존재하지 않는 파일은 `BLOCKED` 사유가 아니다(1라운드에 `critique_v<n-1>.md`가 없는 것은 정상이다). 그러나 **주입 목록에 올라온 파일을 열지 못하면 그것은 `BLOCKED`다** — 목록에 올렸다는 것은 오케스트레이터가 그 파일의 존재를 선언했다는 뜻이고, 그것 없이 진행하면 리셋 이어받기·승인된 피벗·라운드 비교가 조용히 누락된다. 오케스트레이터는 `BLOCKED`를 받으면 **경로를 고쳐 재디스패치**한다. 그 산출물을 채택하거나 다음 단계로 넘어가지 않는다. **조용한 성공** — 계약·루브릭·앵커를 읽지 못한 채 그럴듯한 산출물을 내는 것 — 이 이 하네스의 가장 위험한 실패 모드다. 이 스킬이 보드에서 막으려는 실패(근거 없이 그럴듯한 것)와 같은 형태이기 때문이다.

## 활성화 흐름

**12단계. 이터레이션 상한 = 5–15 라운드(범위. 단일 값으로 고정하지 않는다).**

1. **진입.** `/tvl <요청>` 또는 트리거 문구. 요청이 "이 작업", "방금 그거" 류면 직전 대화 맥락을 재료로 삼는다. post URL이 오면 **마지막 세그먼트가 postId**다 (`/o/{org}/{ws}/{proj}/{boardId}/post/{postId}`). 여기서 **`SKILL_ROOT`·`RUN_DIR`을 먼저 확정한다**(앞 절). — `/tvl` 슬래시 커맨드는 `commands/tvl.md`를 `~/.claude/commands/tvl.md` 로 심링크했을 때만 존재한다. 없으면 트리거 문구로 진입하고, 설치는 `references/mcp-setup.md` §6으로 안내한다.
2. **【G1】 MCP 연결 게이트.** `board_*` 도구가 세션에 존재하는지 확인한다. 없으면 `references/mcp-setup.md` 안내로 분기하고 **여기서 멈춘다 — 쓰기 경로에 진입하지 않는다.** 있으면 `board_list_boards()` 스모크 테스트로 토큰·연결을 실증한다.
3. **【G2】 폐기 — 건너뛴다.** tavlet 레포 핸드오프 게이트였다. 판정 조건과 핸드오프 대상이 모두 `ff3fa1f` 에서 사라져 이 단계는 수행하지 않는다(위 「경계 규칙」).
4. **【G3】 테넌트 확정 게이트.** `.tavlet.json` 로드(없으면 스키마대로 생성 제안 — gitignore 등재 확인 선행). 2단계의 `board_list_boards()` 반환에 대상 `boardId`가 **실재하는지** 대조하고 `baseUrl`·`boardVisibility`를 확정한다. **확정 전 쓰기 금지.**
5. **세션 사실 수집.** 이 세션에서 **실제로 수행·관측된 것만** 모은다 — 변경 파일 경로(가능하면 `파일:라인`), `git log --oneline -n` / `git show --stat <hash>`로 확인한 커밋 해시, 실제 실행한 명령과 그 출력, 에러 원문. 확인하지 못한 것은 **"미검증"으로 분류**하고 삭제하지 않는다. **추정 금지.** 1차 스크럽(G7)을 여기서 수행한다.
6. **【G4】 읽기 정찰 게이트.** `board_list_posts`를 **서로 다른 `q` 2회 이상** 호출하고 후보를 `board_get_post`로 본문 대조해 **신규/기존을 판정**한다. 필요에 따라 `board_get_taxonomy`(실제 카테고리·태그 id), `board_list_statuses`(실제 컬럼), `board_list_tasks`(현재 task 분포)를 조회한다. **이 정찰 없이 `board_create_post` 경로로 갈 수 없다.**
7. **Planner 디스패치** (`Agent`, `{SKILL_ROOT}/references/planner-prompt.md`) — 프롬프트 앞에 **디스패치 주입 블록**을 붙이고 5·6단계 결과를 함께 전달 → `{RUN_DIR}/spec.md`(보드 변경 계획). `NEED_EVIDENCE`가 오면 사용자에게 그 증거를 요청하고 5단계로 되돌아간다. `BLOCKED: <경로>`가 오면 **경로를 고쳐 재디스패치**한다.
8. **Generator 디스패치** (`Agent`, `{SKILL_ROOT}/references/generator-prompt.md`) — 주입 블록 + `{RUN_DIR}/spec.md` → `{RUN_DIR}/drafts_v<n>.md` + `{RUN_DIR}/generator_report_v<n>.md`. **단일 연속 세션(스프린트 없음). 쓰기 도구 호출 없음.** `HANDOFF_NEEDED: <handoff 파일명>`이 오면 **새 Generator 세션**을 띄운다(압축 금지). **그 라운드의 handoff 파일을 전부, 생성 순서대로 넘긴다** — 주입 블록 읽을-파일 목록에 각각의 절대 경로를 올려 디스패치한다. 두 번째 리셋의 `handoff_v<n>b.md`는 첫 번째를 **대체하지 않는다**: 앞 파일에만 있는 완성 초안 목록이 누락되면 새 세션이 그 초안을 다시 쓴다. 이 시점에는 쓰기가 아직 한 건도 실행되지 않았으므로 handoff 에 **실행 기록은 없다** — 그것은 12단계 `execution_state.md`의 소관이다. `BLOCKED`도 같은 처리 — 경로를 고쳐 재디스패치.
9. **Evaluator 디스패치** (`Agent`, `{SKILL_ROOT}/references/evaluator-prompt.md`) — 주입 블록 + `spec.md` + `drafts_v<n>.md` + `generator_report_v<n>.md` → 적대적 프로브 7종 실행 → `{RUN_DIR}/critique_v<n>.md`(PASS/FAIL). Evaluator는 읽기 도구만 쓴다. `BLOCKED`가 오면 **그 라운드의 채점을 채택하지 않는다** — 루브릭·앵커를 못 읽은 채점은 보정되지 않은 채점이다.
10. **루프 제어.** PASS → 11단계. FAIL이고 라운드 < 상한 → `critique_v<n>.md`를 넘겨 8단계로(Strategic Decision: REFINE / PIVOT / ESCALATE). `REDIRECT:` 나 `design_memo_v<n>.md`가 있으면 피벗 전에 승인하거나 수정하고, **승인한 메모의 절대 경로를 다음 라운드 주입 블록에 올려 넘긴다**(다음 라운드 관점의 이름은 `design_memo_v<n-1>.md`다). 넘기지 않으면 다음 라운드 Generator 는 승인 사실을 모른 채 방향 전환 금지 하드룰에 걸린다. **이전 라운드의 `critique_v*.md`·`drafts_v*.md`를 지우거나 덮어쓰지 않는다** — 최선 라운드 판정의 근거다. **상한 5–15를 지키되 점수가 여전히 오르는 중이면 5에서 반사적으로 멈추지 않는다.** `DEADLOCK`이면 사용자에게 증거 보강 또는 스펙 판단을 요청하고 멈춘다.
11. **【G5·G6·G7】 승인 게이트 — 필수·대체 불가.** PASS된 초안을 사용자에게 제시한다. 쓰기 7종 **각각**에 대해 **전송될 정확한 인자 JSON + 대상 보드명/URL**을 보여준다(**요약본 금지**). `baseUrl`이 localhost가 아니면 **"프로덕션 대상"**, `boardVisibility`가 `PUBLIC`이면 **"외부 독자가 읽는 공개 보드 — 댓글도 공개"** 경고를 함께 표시하고 별도 확인을 받는다. `board_create_suggestion`·`board_create_release_draft` 항목에는 **"반환 id만 · 재조회 수단 없음"** 을 함께 표기한다(아래 12단계). 스크럽 결과를 보고한다. **사용자의 명시 승인 이전에는 어떤 쓰기 도구도 호출하지 않는다.** 수정 요청이 오면 반영 후 다시 미리보기한다.
12. **실행 → 사후 검증 → 보고.** 이 단계의 작성자는 **오케스트레이터(이 세션)** 다. 쓰기를 호출하는 유일한 주체이므로, 무엇이 실제로 실행됐는지 아는 주체도 여기뿐이다.
    - **【첫 쓰기 이전】 `{RUN_DIR}/execution_state.md` 초기화.** 승인된 쓰기 **전건**을 실행 순서대로 적고 전 항목을 `PENDING`으로 둔다(재개하는 **다른** 세션이 읽을 파일이므로 형식을 임의로 바꾸지 않는다. 항목당 아래 블록 4줄 — 인자 JSON 에 `|` 가 흔히 섞이므로 한 줄 구분자 표는 쓰지 않는다:

      ```
      ## <순번>. <도구명> — 대상: <boardId 또는 postId>
      상태: PENDING
      인자: <승인된 JSON 한 줄>
      기준선: <board_add_comment 항목만. **초기화 시점에는 반드시 "미기입"으로 두고, 그 항목을 호출하기 직전에**
               board_get_post 로 읽은 commentCount 로 채운다. 그 외 항목은 "해당 없음">
      ```

      `기준선`은 재개 시 댓글 반영 여부를 판정하는 **유일한 수단**이다. 값이 없으면(`미기입`) 그 항목은 대조가 아니라 사용자 확인으로 간다. **초기화 시점의 값을 미리 적어 두지 않는다** — 그 사이에 제3자가 단 댓글이 증가분을 만들어, 실행되지 않은 댓글을 "반영됨"으로 오판하게 한다). **이 파일을 만들기 전에 첫 쓰기를 호출하지 않는다.** `PENDING`·`DONE`·`FAILED`·`CANCELLED`·`UNKNOWN`은 **이 파일 안에서만 쓰는 실행 추적 라벨**이며 board 의 task status(`TODO`·`DOING`·`DONE`·`DROPPED`)·post status 와 **다른 집합**이다 — 보드로 전송하지 않는다.
    - **실행:** 승인된 인자를 **그대로**, 의존 순서대로 호출한다. **각 호출 직후 즉시** 해당 항목을 `DONE(<반환 id/URL>)` 또는 `FAILED(<반환 원문 그대로>)`로 갱신한다 — 다음 호출로 넘어가기 전에 갱신한다. 갱신 전에 세션이 끊기면 그 항목은 `PENDING`으로 남는데, **`PENDING`은 "실행 안 됨"이 아니라 "실행 여부 미상"이다** — 재개 시 아래 대조 절차로만 판정한다.
    - **실패 판정:** 반환이 `isError`이거나 반환 텍스트가 `Error:` 로 시작하거나 `[board] <숫자 status> <METHOD> <path>:` 패턴을 포함하면 **실패다.** 원문을 그대로 표면화하고 **중단** — 남은 항목을 전부 `CANCELLED`로 표시한 뒤 후속 쓰기를 취소하고, 이미 실행된 것과 취소된 것을 분리해 보고한다.
    - **중단 후 재개.** 실행 도중 세션이 끊기거나 컨텍스트를 리셋해야 하면, 재개하는 세션은 **`execution_state.md`를 가장 먼저 읽는다.** `DONE` 항목은 **절대 재실행하지 않는다.** `FAILED`로 중단된 실행이면 `CANCELLED` 항목을 그냥 이어가지 않는다 — 실패 원문을 사용자에게 표면화하고 **11단계 승인 게이트로 돌아간다.** 중단은 의도된 정지이지 일시 중지가 아니다.
      **`PENDING` 잔존 대조(필수).** `PENDING` 항목이 하나라도 남아 있으면 — 그리고 `execution_state.md` 자체가 없는데 쓰기가 이미 나갔을 가능성이 있으면 — **그대로 실행하지 않는다.** 먼저 읽기 도구(`board_list_posts` · `board_get_post` · `board_list_tasks` · `board_list_release_candidates`)로 그 쓰기가 보드에 반영됐는지 확인한다. **어떤 도구로 무엇을 대조할 수 있는지는 `references/board-tool-contract.md` §3-1 이 정본이다** — 여기서 다시 나누지 않는다. 결과는 셋 중 하나다:
      - **반영 확인** → 항목을 `DONE(<확인한 id/URL> · 사후 대조로 확정)`으로 고치고 건너뛴다.
      - **미반영 확인** → 그 항목만 실행한다.
      - **판정 불가** → 재실행하지 않는다. 항목을 `UNKNOWN(<판정 불가 사유> · 사용자 확인 필요)`로 적고 사용자에게 실행 여부를 묻는다. 답을 받으면 `DONE(<사용자 확인>)` 또는 실행으로 확정한다. 판정 불가가 나오는 자리는 §3-1 기준으로 `board_create_suggestion`(조회 도구 부재)과 **기준선이 없는 `board_add_comment`** 다 — `commentCount` 만으로는 그 댓글이 내가 쓴 것인지 남이 쓴 것인지 구별되지 않으므로, 기준선 없는 증가를 반영으로 판정하면 거짓 완료 보고(C2 위반)가 된다. `board_create_release_draft` 는 **판정 불가가 아니다** — 포함된 post 의 `affectedRelease` 와 `board_list_release_candidates` 소거로 확인한다. 참고로 초안이 이미 등록된 뒤의 재실행은 **409 가 아니라 400** 으로 막힌다 — 연결된 post 가 `affectedReleaseId` 를 이미 가지므로 `유효하지 않은 post 입니다(프로젝트 밖·미완료·기할당·병합됨)` 이 먼저 나온다(`services/releases.ts:426-434`). `version` 중복 409 는 그 검사를 통과한 **다른** post 묶음으로 같은 version 을 다시 낼 때의 얘기다. 어느 쪽이든 재실행 판단의 근거는 대조이지 서버 거절이 아니다.

      확인 없는 재실행이 중복 post·중복 댓글을 프로덕션에 남긴다. 묻는 쪽이 언제나 옳다.
    - **사후 read-back — 쓰기 7종 중 5종만 가능하다.** `board_create_post`·`board_create_tasks`·`board_update_task_status`·`board_add_comment`·`board_set_status`는 `board_get_post` · `board_list_tasks`로 재조회해 승인 내용과 대조한다(단 댓글은 `commentCount` 증가까지만 확인되고 **본문은 재조회되지 않는다**). 불일치는 숨기지 않고 그대로 보고한다.
    - **read-back 불가 2종.** `board_create_suggestion`·`board_create_release_draft`는 결과를 조회하는 도구가 14종 안에 **없다.** 이 둘은 **반환된 id를 그대로 보고하고 "재조회 수단 없음"을 명시**한다 — 단 중단 후 사용자 확인으로 확정된 항목은 반환 id 가 세션과 함께 소실됐으므로 `DONE(id 미상 · 사용자 확인 · 재조회 수단 없음)`으로 적는다. 없는 id 를 지어내지 않는다 — `execution_state.md`에도 `DONE(<반환 id> · 재조회 수단 없음)`으로 적어 read-back 수행분과 구분한다. 도구별 수단과 근거는 `references/board-tool-contract.md` §3-1. **검증하지 않은 것을 검증했다고 보고하는 것은 이 스킬의 C2 위반이다.**
    - **보고:** postId · post URL · 커밋 트레일러 `[tv:<taskId>]` · 실행/미실행 목록 · **read-back 수행분과 "재조회 수단 없음" 항목의 분리 기재**. **최종 보고와 사후 read-back의 근거는 기억이 아니라 `execution_state.md`다** — read-back 대상도 이 파일의 `DONE` 항목에서 뽑고, 보고의 실행/미실행 구분도 이 파일의 상태값을 그대로 옮긴다 — `UNKNOWN` 항목은 **"실행 여부 미상 · 사용자 확인 대기"** 로 별도 줄에 적는다. 실행 또는 미실행 어느 쪽으로도 반올림하지 않는다. 상한 도달까지 PASS하지 못했으면 **최선 라운드**(마지막 라운드가 아닐 수 있다)의 초안과 그 라운드의 `critique_v<n>.md`, 남은 갭을 정직하게 제시하되 **승인 없이는 여전히 실행하지 않는다.**

**사용자 확인 게이트(전부 필수, 조용히 생략 불가):** (a) 3단계 tavlet 레포 핸드오프 확정, (b) 4단계 테넌트 확정, (c) 11단계 쓰기 승인 + 프로덕션·공개면 확인.

## 안전 게이트

| # | 게이트 | 차단 조건 | 통과 조건 |
|---|---|---|---|
| **G1** | **MCP 연결** | `board_*` 도구가 세션에 없음 | `references/mcp-setup.md` 안내로 분기. **쓰기 경로 진입 금지.** 연결 후 `board_list_boards()` 스모크 테스트 성공 |
| ~~**G2**~~ | ~~tavlet 레포 핸드오프~~ | **폐기** — 판정 조건·핸드오프 대상이 tavlet `ff3fa1f` 에서 삭제됨 | 수행하지 않는다. 번호는 하위 참조 보호를 위해 비워 둔다 |
| **G3** | **테넌트 확정** | 대상 org/board 미확정 | `.tavlet.json` 로드 또는 사용자 명시 + `board_list_boards()` 반환에 해당 boardId **실재 확인**. 확정 전 쓰기 금지 |
| **G4** | **중복 정찰 선행** | `board_list_posts` 조회 없이 `board_create_post` 시도 | 서로 다른 `q` **2회 이상** 조회 + 후보를 `board_get_post`로 본문 대조 + "신규/기존" 판정 근거 기록 |
| **G5** | **쓰기 승인 (human checkpoint · 대체 불가)** | 미리보기 없음 · 요약본 미리보기 · 승인 미수신 · 승인 후 인자 변경 | 쓰기 7종 각각에 대해 **전송될 정확한 인자 JSON + 대상 보드/URL**을 제시하고 명시 승인 수신 |
| **G6** | **프로덕션·공개면 확인** | `baseUrl`이 localhost가 아님(= 프로덕션 `tavlet.io`) 또는 대상 보드가 **공개 가시성** | 미리보기에 "프로덕션 대상"·"외부 독자가 읽는 공개 보드" 경고를 명시하고 **별도 확인**을 받는다 |
| **G7** | **비밀·개인정보 스크럽** | 초안 본문에 PAT(`tvl_`/`hhb_` 접두사)·`.env` 값·API 키·Bearer 토큰·개인 이메일·사용자 홈 절대경로·(공개 보드 대상 시) 미공개 내부 정보가 잔존 | 미리보기 **이전에** 스크럽 스캔을 수행하고 결과를 보고. 잔존 시 하드 FAIL |

**G6·G7이 함께 필요한 이유:** 이 스킬은 세션의 **에러 원문·로그·명령 출력**을 그대로 보드 본문으로 옮긴다. 이 재료는 시크릿·토큰·개인정보를 자주 포함한다. 그리고 MCP `board_add_comment`는 `{ postId, body }` 만 노출한다 — **`internal`(팀 전용) 플래그가 없으므로 MCP 경유 댓글은 전부 공개 댓글이다**(근거: 원격 `src/lib/mcp/board-tools.ts` 의 `board_add_comment` inputSchema 가 `{ postId, body }` 뿐이고 서비스에 `{ body }` 만 전달. stdio 판도 동일 — `server.ts` 도구 설명 "게시글에 댓글 작성(공개)", `board-client.ts:56-57`. `src/lib/validation/posts.ts:47`에 `internal` 필드가 존재하지만 MCP 도구는 노출하지 않는다). 정본 보드 중 `M6Nz6bWCr2Ow`는 공개 로드맵이다. 스크럽 게이트 없이는 이 스킬이 유출 경로가 된다.

**보드 가시성은 어떤 `board_*` 도구도 반환하지 않는다.** `board_list_boards`가 주는 `kind`는 `FEATURE`·`BUG`·`FEEDBACK`(보드 종류)이지 공개 여부가 아니다. 공개 여부의 정본은 `.tavlet.json`의 `boardVisibility` 이며, 그 값이 없으면 **`PUBLIC`으로 간주(안전 측 기본값)** 하고 사용자에게 확인한다. 자세한 근거는 `references/board-tool-contract.md` §가시성.

## 쓰기 도구 7종 × 승인 게이트 배치

**쓰기 7종은 예외 없이 이 배치를 따른다.** 하나라도 게이트 밖에 있으면 Evaluator 프로브 6이 즉시 FAIL을 낸다.

| # | 쓰기 도구 | 미리보기에 반드시 포함할 것 | 호출 시점 |
|---|---|---|---|
| 1 | `board_create_post` | 전체 `{ title, body, boardId, categoryIds?, tagNames? }` JSON + 보드명·보드 URL + 프로덕션/공개면 표기 | 승인 후 |
| 2 | `board_create_tasks` | 전체 `{ postId, items:[{title, detail?}] }` JSON (items **전건**, 요약 금지) | 승인 후 · post 생성 성공 후 |
| 3 | `board_update_task_status` | 전체 `{ postId, taskId, status }` JSON + 해당 task의 현재 상태 | 승인 후 |
| 4 | `board_add_comment` | 전체 `{ postId, body }` JSON (body **전문**) + **"이 댓글은 공개"** 표기 | 승인 후 |
| 5 | `board_set_status` | 전체 `{ postId, status }` 또는 `{ postId, columnId }` JSON + 현재 상태 + task 상태 분포 | 승인 후 · task 전이 후 |
| 6 | `board_create_suggestion` | 전체 `{ postId, rationale, categoryIds?, tagIds?, kindNote?, priority?, duplicates? }` JSON + **"반환 id만 · 재조회 수단 없음"** 표기 | 승인 후 |
| 7 | `board_create_release_draft` | 전체 `{ projectId, version, name?, body, entries:[{ title, body, type, postIds }] }` JSON + **"발행되지 않는 초안"** · **"반환 id만 · 재조회 수단 없음"** 표기 | 승인 후 |

**읽기 7종**(`board_list_boards` · `board_list_posts` · `board_get_post` · `board_get_taxonomy` · `board_list_statuses` · `board_list_tasks` · `board_list_release_candidates`)은 게이트 없이 자유롭게 호출한다.

## 파일 핸드오프 계약

역할 간 통신은 **파일로만** 한다. 실행 산출물은 전부 **`RUN_DIR` 바로 아래**에 쓴다 — 스킬 폴더 안에 남기지 않는다. 아래 경로는 전부 `{RUN_DIR}/` 기준이며, **세 역할이 읽고 쓰는 파일**은 디스패치 시 **절대 경로로 전개해** 프롬프트에 주입한다. 마지막 행 `execution_state.md`만 예외다 — 오케스트레이터 전용이므로 어떤 역할 프롬프트에도 주입하지 않는다.

| 파일 | 작성자 | 내용 |
|---|---|---|
| `spec.md` | Planner | 기록 의도·증거 기준 · 보드/테넌트 컨텍스트와 세션 사실 목록 · 쓰기 단위 목록 · Definition of Done |
| `drafts_v<n>.md` | Generator | 라운드 `n`의 쓰기 초안 묶음 (도구별 4종 세트: 대상 · 정확한 인자 JSON · 증거 출처 · 선행 조건) |
| `generator_report_v<n>.md` | Generator | Strategic Decision · 초안 목록 · 증거 대조표 · 미검증 항목 · 계약 검증 · 스크럽 결과 · 자기평가 · 실행 순서 |
| `critique_v<n>.md` | Evaluator | Verdict · C1–C5 점수와 증거 인용 · 프로브 7종 결과 · Blocking Issues · Iteration Quality Note · 선택적 `REDIRECT:` |
| `design_memo_v<n>.md` | Generator | PIVOT 제안 + `critique_v<n-1>.md` 근거 인용 (승인 대기) |
| `handoff_v<n>.md` (재리셋 시 `handoff_v<n>b.md` · `handoff_v<n>c.md`) | Generator | 8단계 초안 작성 중 컨텍스트 불안 시 — **초안 진행 상태만**: 완성한 쓰기 초안 · 남은 초안 · 재확인이 필요한 증거. **쓰기 실행 기록은 여기 들어오지 않는다** |
| `execution_state.md` | **오케스트레이터(메인 세션)** | 12단계 실행 상태의 정본 — 승인된 쓰기 전건과 각 항목의 `PENDING` / `DONE(<id·URL>)` / `FAILED(<반환 원문>)` / `CANCELLED` / `UNKNOWN(<사유> · 사용자 확인 필요)`. 첫 쓰기 **이전에** 초기화하고 **각 호출 직후** 갱신한다. 라운드 접미사 없음(실행은 런당 1회) |

**두 기록의 소유자가 다른 이유.** 쓰기 7종을 호출하는 것은 오케스트레이터뿐이다(위 「역할 분리」). 따라서 "무엇이 실제로 실행됐는가"를 아는 주체도 오케스트레이터뿐이며, Generator 가 쓰는 `handoff_v<n>.md`에 실행 기록을 요구하면 그 칸은 영구히 빈칸이 된다. **초안 진행은 Generator 가, 실행 상태는 오케스트레이터가** 각자 아는 것만 남긴다.

**`_v<n>` 접미사는 장식이 아니다.** 라운드 산출물을 덮어쓰면 "최선 라운드가 마지막 라운드가 아닐 수 있다"는 판정을 할 근거가 사라진다. 라운드가 끝나도 이전 파일을 지우지 않는다.

**`sprint_contract.md`는 없다.** 이 스킬은 Simplified tier이며 스프린트 구조를 통째로 제거했다 — 스프린트 계약도, 스프린트별 Evaluator도, `sprint-playbook.md`도 없다.

## 컨텍스트 리셋 정책

**리셋 ≠ 압축.** 압축(compaction)은 불안 상태를 보존한다. 새 세션만이 그것을 지운다.

Opus 5에서는 단일 연속 Generator가 초안 묶음을 완주하는 것이 기대값이다. 그래도 다음 **관측 가능한 불안 신호 5종** 중 하나라도 나타나면, 현재 초안을 깨끗이 마무리하고 `RUN_DIR`에 handoff 파일을 쓴 뒤 `HANDOFF_NEEDED: <그 파일명>`을 출력한다(파일명 규칙은 아래).

1. 증거를 다시 확인하지 않고 앞서 쓴 초안을 재요약하기 시작한다.
2. 초안 본문에 뭉개기 표현이 등장한다 — "등 다수", "기타 여러 파일", "전반적으로", "관련 파일들".
3. 후반 초안의 증거 밀도가 앞부분보다 눈에 띄게 떨어진다(앞: `파일:라인` + 커밋 해시, 뒤: 제목만).
4. "자세한 내용은 생략" / "간략히" 를 쓰려 한다.
5. 쓰기 인자 미리보기를 축약하려 한다 (= 승인 게이트 위반의 전조).

**handoff 에는 초안 진행 상태만 적는다.** 8단계 시점에는 쓰기가 한 건도 실행되지 않았고 Generator 는 쓰기 도구를 호출하지 않는다 — 적을 실행 기록이 애초에 없다. 세 가지를 적는다:

- **완성한 쓰기 초안** — 초안 번호 · 도구명 · `drafts_v<n>.md` 안의 위치 · 증거 확인 완료 여부
- **남은 초안** — 초안 번호 · 도구명 · 아직 필요한 것(증거 · 선행 조건)
- **재확인이 필요한 증거** — 좌표를 다시 확인하지 못한 채 남긴 주장

**파일명 — 같은 라운드의 두 번째 리셋은 앞의 handoff 를 덮어쓰지 않는다.** `handoff_v<n>.md` → `handoff_v<n>b.md` → `handoff_v<n>c.md` 순으로 접미 문자를 붙인다. 첫 리셋에만 기록된 완성 초안 목록이 사라지면 세 번째 세션이 그 초안을 다시 쓴다. 이어받는 세션은 그 라운드의 handoff 파일을 **전부 이 순서대로** 읽고, 오케스트레이터는 주입 블록에 **존재하는 것을 전부** 열거한다(8단계).

**실행 중단의 멱등성은 다른 파일이 맡는다.** 승인된 쓰기가 **일부만 실행된 상태**에서의 중단은 **12단계에서만** 일어날 수 있고, 그 정본은 오케스트레이터가 쓰는 `execution_state.md`다. 재개 세션은 그 파일을 가장 먼저 읽고 `DONE` 항목을 재실행하지 않으며, **`PENDING` 은 "미실행"이 아니라 "실행 여부 미상"이므로 12단계의 「`PENDING` 잔존 대조」를 거친 뒤에만 손댄다.** 이 기록이 없으면 중복 post·중복 댓글이 프로덕션에 남는다.

## 이터레이션 지혜

- **상한은 범위로 둔다 — 5–15 라운드.** 단일 값으로 고정하면 그 숫자가 품질 목표를 대체한다.
- **낮은 끝에서 반사적으로 멈추지 않는다.** 점수가 여전히 오르는 중이면 5에서 멈추지 말고 15까지 간다. 원 사례연구에서 **아홉 번째 반복까지는 무난한(clean, dark-themed) 결과**였고, 접근을 통째로 갈아엎는 결정적 도약은 **열 번째 사이클에서** 나왔다. 아홉 번의 "깔끔한 산출물"이 열 번째의 조건이었다는 뜻이다.
- **시간에 관대하라.** 한 번의 완주에 최대 ~4시간까지 허용한다. 여기서 한 라운드는 **초안 텍스트를 읽는 값싼 심사**이고, 실제 쓰기는 PASS 이후 승인 시점에 **한 번만** 일어난다. 라운드를 늘려도 프로덕션 부작용은 늘지 않는다.
- **중간 라운드가 최종 라운드보다 나을 수 있다.** Evaluator의 Iteration Quality Note를 진지하게 읽는다. 최종 제출은 **마지막 라운드**가 아니라 **최선 라운드**여야 한다.

## V1 vs V2 모델 가이드

| 모델 등급 | 컨텍스트 불안 | 권장 tier | 비고 |
|---|---|---|---|
| **Sonnet 4.5** | 강함 — 조기 마무리 | Full (V1) | 더 작은 단위, 더 공격적인 Evaluator, 단호한 컨텍스트 리셋. 승인 게이트는 그대로 유지. |
| **Opus 4.5** | 대부분 제거 | Simplified (V2) | 다시간 일관 세션 가능. 스프린트 분해를 뺄 수 있다. |
| **Opus 4.6** | 제거. 계획·롱컨텍스트·디버깅 개선 | Simplified 또는 single-session | 2시간 이상 빌드 지속 가능. 각 구성요소를 재검토해 하중이 없는 것을 뺀다. |
| **Opus 4.8** | 제거 | Simplified | 단일 연속 Generator로 충분. |
| **Opus 5** (이 스킬의 목표) | **제거** | **Simplified** | 단일 연속 Generator + 라운드 종료 시 Evaluator 1회, 스프린트 없음. **승인 게이트는 영구다** — 컨텍스트 한계가 아니라 **외부 시스템에 대한 부작용 권한** 문제이므로 모델 업그레이드로 사라지지 않는다. |

**Evaluator의 가치는 고정된 예/아니오가 아니다.** 과제와 모델의 경계에 달려 있다. 여기서는 Opus 5에서도 값을 한다: 2× 축(증거 구체성·세션 사실성)이 바로, 압박이 없으면 강한 모델도 요약 어휘로 미끄러지는 지점이고, 그 미끄러짐의 결과가 **프로덕션 보드에 남는 거짓 기록**이기 때문이다.

## 원칙

- **하네스의 모든 구성요소는 모델 능력에 대한 가정을 인코딩한다.** 모델을 올릴 때는 구성요소를 **한 번에 하나씩** 제거하고 결과를 관찰한다.
- **급진적 단순화(한 번에 다 빼기)는 실패한다.** 체계적으로 하나씩 빼면서 무엇이 하중을 지고 있었는지 확인한다.
- *"find the simplest solution possible, and only increase complexity when needed."* (Anthropic, *Building Effective Agents*) — 이 스킬이 Simplified tier인 이유이고, 스프린트 계약을 넣지 않은 이유다.
- **하네스는 목표 모델로 직접 실험하고 트레이스를 읽어 조정한다.** 추측으로 게이트를 늘리지 않는다.

## Evaluator 튜닝 워크플로

보정되지 않은 Evaluator는 너무 관대하다. 초기 실행은 초안으로 취급한다. **(a)–(d)는 운영 절차이며, 하나라도 건너뛰면 결함이다.**

**(a) 완료된 런의 `critique_v<n>.md` 전건을 실제 결과와 나란히 읽는다.** 라운드별 파일이 남아 있으므로 라운드 간 점수 변화도 함께 본다. 실제로 등록된 post는 `board_get_post`로, task는 `board_list_tasks`로 재조회해 옆에 놓는다(**댓글 본문은 재조회되지 않는다** — 승인 시점에 기록해 둔 인자를 쓴다). 각 점수마다 묻는다 — *까다로운 시니어 리뷰어와 보드 큐레이터가 같은 점수를 줬겠는가?*

**(b) 발산 패턴을 식별한다.** 이 도메인의 전형적 드리프트:
- 파일 경로 1건만 있어도 C1에 4점을 준다(라인·커밋·명령 출력 없이).
- 인용된 커밋 해시의 실재를 `git`으로 확인하지 않고 통과시킨다.
- 프로브 4(중복 재정찰)를 생략하고 Generator의 "중복 없음"을 신뢰한다.
- **요약본 미리보기를 승인 게이트 충족으로 인정한다.**
- `tagNames`/`tagIds`, task status/post status 혼동을 잡지 못한다.
- `generator_report_v<n>.md`의 자기평가를 그대로 옮겨 적는다(독립 채점 실패).
- **프로브 6(게이트 감사)을 형식적으로 통과 처리한다** — 절차 배치만 보고 "7종 다 있다"로 넘기면서, 미리보기에 실린 인자가 **전송될 인자 전문인지**·read-back 불가 2종 표기가 있는지를 초안 단위로 대조하지 않는다. 이 프로브는 라운드마다 같은 답이 나오기 쉬워 가장 먼저 형해화된다.
- 어떤 기준에 3점을 주고 verdict를 PASS로 낸다(현행 로직에서 **3점 이하는 FAIL**이다).

**(c) 놓친 사례를 구체 반례 앵커로 추가한다.** `references/evaluator-calibration.md`의 해당 기준·해당 점수대에 넣거나 `references/evaluator-prompt.md`의 프로브 문구를 강화한다. 예 — "커밋 해시 `a3f91c2`를 검증 없이 통과시켰다 → 프로브 2에 `git cat-file -e <hash>^{commit}` 확인을 명령형으로 명시" · "이 다이제스트에 C1 4점을 줬으나 명령 출력이 없다 → C1의 3/5 앵커로 추가".

**(d) 같은 입력으로 재실행해 이전 누락을 이제 잡는지 확인한다.** 여전히 놓치면 (c)로 돌아간다. Evaluator의 판정이 신중한 사람 전문가의 심사와 상관하고, 제기하는 모든 blocking issue가 재현 가능해지면 튜닝을 멈춘다.

## 마무리 가이드

- **모델을 올릴 때는 하네스 구성요소를 한 번에 하나씩 제거한다.** 먼저 뺄 후보: 라운드 상한 하향, Evaluator 프로브 축소. 각각 제거 후 실제 런의 `critique_v<n>.md`와 등록 결과를 비교한다.
- **하네스 공간은 줄어드는 게 아니라 이동한다.** 모델이 좋아질수록 "완주시키기 위한 비계"는 줄고, "무엇이 좋은가를 정의하고 검증하는 장치"가 남는다. 여기서는 루브릭 C1·C2와 프로브 7종이 그 남는 부분이다.
- **승인 게이트(G5)와 프로덕션·공개면 확인(G6), 스크럽(G7)은 영구다.** 절대 제거 후보에 넣지 않는다. 이것들은 모델의 약점을 보완하는 장치가 아니라, **외부 시스템에 대한 부작용 권한을 사람에게 남겨두는 장치**다.

## 참조 파일

경로는 전부 **`{SKILL_ROOT}/` 기준**이다. 서브에이전트에게 넘길 때는 절대 경로로 전개한다.

| 파일 | 언제 읽는가 |
|---|---|
| `references/board-tool-contract.md` | **항상.** 세 역할 전부 + 오케스트레이터. 도구 14종의 정본 계약 + §3-1 read-back 수단 |
| `references/planner-prompt.md` | 7단계 Planner 디스패치 시 |
| `references/generator-prompt.md` | 8단계 Generator 디스패치 시 |
| `references/evaluator-prompt.md` | 9단계 Evaluator 디스패치 시 |
| `references/rubric.md` | Generator 자기평가 · Evaluator 채점 |
| `references/evaluator-calibration.md` | Evaluator 채점 전 · 튜닝 (c) |
| `references/mcp-setup.md` | G1 미연결 시 · 최초 설치·배포 시 |
| `commands/tvl.md` | `/tvl` 슬래시 커맨드 정본 소스. **이 파일만으로는 아무 효과가 없다** — `~/.claude/commands/tvl.md` 심링크(`references/mcp-setup.md` §6)를 만들어야 `/tvl`이 존재한다. 심링크 없이도 트리거 문구로 스킬은 활성화된다 |
