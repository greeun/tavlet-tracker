# MCP 배선 · `.tavlet.json` · 배포

게이트 **G1(MCP 연결)** 이 막혔을 때, 그리고 이 스킬을 처음 설치할 때 읽는다.

tavlet은 4계층 테넌시(Organization → Workspace → Project → Board)를 가진 멀티테넌트 SaaS다. **org마다 PAT가 다르다.** 이 문서의 절차는 그 사실을 전제로 한다.

이 문서에서 `<WORKSPACE>` 는 tavlet 및 claude-skills 저장소를 체크아웃한 워크스페이스 디렉터리의 절대 경로다 — 각자의 환경 값으로 치환한다.

---

## 0. 불변 규칙 3개

1. **MCP 등록은 프로젝트(= org/보드) 단위로 분리한다.** org마다 PAT가 다르므로 user 스코프 단일 등록은 금지다 — 한 토큰으로 모든 org를 쓰려는 순간, 그 토큰이 커버하지 않는 보드에는 실패하고 커버하는 보드에는 **의도하지 않은 테넌트로 쓸 위험**이 생긴다.
2. **토큰 값을 git 추적 파일에 절대 쓰지 않는다.** 파일에 쓰기 전 `git check-ignore -v <파일>` 로 무시 대상임을 **확인하고**, 확인되지 않으면 쓰지 않는다.
3. **서버 경로는 tavlet 체크아웃의 절대 경로를 쓴다.** tavlet 레포의 `.mcp.json`은 상대 경로(`agent/mcp/board/server.ts`)이며 **그 레포 안에서만 유효하다.** 외부 레포에서는 반드시:
   ```
   <WORKSPACE>/tavlet/agent/mcp/board/server.ts
   ```

---

## 1. 사전 준비

| 항목 | 확인 방법 |
|---|---|
| tavlet 체크아웃 존재 | 위 절대 경로의 `server.ts` 가 실재하는가 |
| `npx tsx` 실행 가능 | Node 설치 여부. `npx --yes tsx --version` |
| PAT 발급 | tavlet 콘솔 → API 토큰. 신규 접두사는 `tvl_`. 대상 보드에 **WRITE grant**가 포함되어야 한다 |
| 대상 boardId | 보드 피드 URL `/o/{org}/{ws}/{proj}/{boardId}` 의 **마지막 세그먼트** |

PAT 접두사 `tvl_`(신규) · `hhb_`(레거시, 검증 수용 전용). **두 접두사 모두 스크럽 대상 문자열이다** — 초안 본문·로그·설정 예시 어디에도 실제 값을 남기지 않는다.

---

## 2. 등록 방식 3안

셋 중 하나를 고른다. **어느 안이든 마지막에 §4 스모크 테스트로 실증한다.**

> 아래 문법(특히 `${VAR}` 환경변수 치환과 `claude mcp add` 의 `--scope` 플래그)은 Claude Code 버전에 따라 다를 수 있다. **문법이 맞다고 단정하지 말고, 스모크 테스트 통과 여부로 판정한다.** 실패하면 §5 진단 분기로 간다.

### A안 — 프로젝트 `.mcp.json` + 환경변수 참조 (권장, 팀 공유 가능)

프로젝트 루트 `.mcp.json`(git 추적)에 서버를 정의하되 **토큰은 환경변수 참조로만** 둔다.

```json
{
  "mcpServers": {
    "board": {
      "command": "npx",
      "args": ["--yes", "tsx", "<WORKSPACE>/tavlet/agent/mcp/board/server.ts"],
      "env": {
        "BOARD_BASE_URL": "https://tavlet.io",
        "BOARD_TOKEN": "${TAVLET_BOARD_TOKEN_TAVLET_IO}",
        "BOARD_DEFAULT_BOARD_ID": "xnUwXGnBK4E2"
      }
    }
  }
}
```

- `BOARD_DEFAULT_BOARD_ID` 는 **편의값일 뿐 테넌트 확정을 대체하지 않는다.** 이 값은 `board_create_post` 에서 `boardId` 를 생략했을 때만 쓰이는 fallback 이며(`server.ts:46`), 대상 보드를 **조용히** 정하는 경로다. 이 스킬은 그 경로를 쓰지 않는다 — 게이트 **G3**(테넌트 확정)은 매 실행마다 `board_list_boards()` 반환에 대상 boardId 가 실재함을 확인하도록 요구하고, 승인 미리보기의 `board_create_post` JSON에는 **언제나 명시 `boardId` 가 실린다**(SKILL.md 「쓰기 도구 7종 × 승인 게이트 배치」 1행). env 값은 그 확인의 근거가 되지 못한다.
- 실제 토큰 값은 셸 환경변수 또는 gitignore된 로컬 env 파일에만 둔다.
- **org마다 변수명을 분리한다** — `TAVLET_BOARD_TOKEN_TAVLET_IO`, `TAVLET_BOARD_TOKEN_<다른ORG>`. 같은 변수명을 재사용하면 어느 org의 토큰이 실려 있는지 알 수 없게 되고, 그것이 테넌트 오등록의 출발점이다.
- 환경변수 치환이 동작하지 않으면(= 스모크 테스트에서 `BOARD_TOKEN 미설정`) B안이나 C안으로 간다.

### B안 — `claude mcp add` (비공유, 가장 안전)

설정을 레포 밖에 두어 **레포에 아무 파일도 남기지 않는다.**

```bash
claude mcp add board \
  --scope local \
  --env BOARD_BASE_URL=https://tavlet.io \
  --env BOARD_TOKEN=<PAT> \
  --env BOARD_DEFAULT_BOARD_ID=xnUwXGnBK4E2 \
  -- npx --yes tsx <WORKSPACE>/tavlet/agent/mcp/board/server.ts
```

- `--scope local`(이 프로젝트에서 나만) 또는 `--scope project`(레포에 `.mcp.json` 생성 — 이 경우 토큰이 파일에 들어가므로 C안의 gitignore 확인이 선행 조건이 된다).
- 플래그 이름이 다르면 `claude mcp add --help` 로 현재 버전의 문법을 확인한다. **셸 히스토리에 토큰이 남는다는 점을 감안한다** — 필요하면 변수로 넘긴다.
- 등록 확인: `claude mcp list`

### C안 — `.mcp.json` 자체를 gitignore (레포가 공유 대상이 아닐 때)

`.mcp.json`에 토큰을 직접 지정하되, **선행 조건**을 반드시 먼저 만족시킨다.

```bash
# 1) gitignore 등재
printf '\n.mcp.json\n' >> .gitignore

# 2) 확인 — 이 명령이 매칭 줄을 출력해야만 다음 단계로 간다
git check-ignore -v .mcp.json
```

`git check-ignore -v` 가 아무것도 출력하지 않으면 **토큰을 쓰지 않는다.** 출력이 나온 뒤에야 A안의 JSON에서 `"BOARD_TOKEN"` 값을 실제 PAT로 바꾼다.

### 어느 안을 고를까

| 상황 | 안 |
|---|---|
| 팀과 공유하는 레포이고 각자 자기 토큰을 쓴다 | **A** |
| 레포에 흔적을 남기고 싶지 않다 / 개인 작업 | **B** |
| 개인 레포이고 환경변수 관리가 번거롭다 | **C** (gitignore 확인 필수) |
| org가 여러 개다 | 프로젝트마다 위 중 하나를 **따로** — 하나의 등록을 여러 org에 재사용하지 않는다 |

---

## 3. `.tavlet.json` — 이 스킬이 규약 소유자다

tavlet `CLAUDE.md:16-17`은 "등록 대상 보드는 `.tavlet.json`(gitignore, 기본 = 내부 작업 보드)이 정한다"고 문서화하지만 **코드 구현체가 없다.** `tavlet-tracker`가 스키마를 정의하고 소비한다.

```jsonc
{
  "baseUrl": "https://tavlet.io",        // 필수. localhost 가 아니면 G6 프로덕션 경고 발동
  "org": "tavlet-io",                    // 필수. URL 조립 + 테넌트 식별 (org SLUG)
  "workspace": "default",                // 필수. URL 조립 (workspace SLUG)
  "project": "default",                  // 필수. project SLUG — projectId 가 아니다
  "projectId": "<board_list_boards.projectId>", // 선택. 릴리스 도구용 DB id.
                                         //   없으면 실행 시 board_list_boards 로 해소하고 기록을 제안
  "boardId": "xnUwXGnBK4E2",             // 필수. 기본 등록 대상
  "boardVisibility": "INTERNAL",         // 필수. PUBLIC | INTERNAL | PRIVATE — G6 공개면 경고 판단의 정본
  "boardKind": "<board_list_boards().kind 를 그대로 옮겨 적는다>",
                                         // 선택. FEATURE | BUG | FEEDBACK 중 하나.
                                         //   ↑ 예시값을 복사하지 말 것. 보드의 실제 kind 는 DB에만 있고
                                         //   소스로 확인할 수 없다. board_list_boards() 반환값을 채운다.
                                         //   용도는 그 반환값과의 대조뿐이며, 공개 여부 판정에는 쓰지 않는다.
  "publicBoardId": "M6Nz6bWCr2Ow",       // 선택. 공개면에 올릴 때만 명시 지정
  "mcpServerName": "board"               // 선택. 기본 "board"
}
```

**토큰은 이 파일에 담지 않는다. 어떤 필드로도 담지 않는다.**

### `boardVisibility` 가 필수인 이유

어떤 `board_*` 도구도 보드의 공개 여부를 반환하지 않는다. `board_list_boards`가 주는 `kind`는 `FEATURE`·`BUG`·`FEEDBACK`(보드 종류)이며 공개 여부가 아니다. DB에는 `Board.visibility`(`PUBLIC`·`PRIVATE`·`INTERNAL`, 기본 `PUBLIC`)가 따로 있지만 에이전트 API DTO에 실리지 않는다. 자세한 근거는 `board-tool-contract.md` §가시성.

→ 따라서 **공개 여부는 운영자가 이 파일에 선언한다.** 값이 없으면 **`PUBLIC`으로 간주(안전 측 기본값)** 하고 사용자에게 확인한다.

### gitignore

tavlet 레포에서는 이미 gitignore 되어 있다(`tavlet/.gitignore:74`). **다른 레포에서는 생성 전에 등재를 먼저 처리한다:**

```bash
printf '\n.tavlet.json\n' >> .gitignore
git check-ignore -v .tavlet.json   # 매칭 줄이 나와야 생성한다
```

파일이 없으면: 사용자에게 대상 보드를 묻고 → `board_list_boards()` 로 실재 확인 → 위 스키마대로 **생성을 제안**한다(gitignore 확인 후). 사용자가 거절하면 이번 세션 한정으로 값을 들고 진행한다.

---

## 4. 스모크 테스트 — 수용 기준

등록 후 **세션을 재시작**하고 `board_list_boards()` 를 한 번 호출한다. 아래 3개가 전부 참이어야 통과다.

- (a) `board_list_boards` 도구가 세션에 **존재**한다
- (b) 반환이 `Error:` 또는 `[board]` 로 **시작하지 않는다** (그리고 `isError` 가 없다)
- (c) 반환 목록에 **대상 boardId가 실재**한다

세 조건을 모두 만족하면 G1 통과다. 하나라도 어긋나면 §5로 간다.

---

## 5. 진단 분기

| 증상 | 원인 | 조치 |
|---|---|---|
| `board_*` 도구가 세션에 아예 없다 | 등록이 안 됐거나 세션 재시작 전 | `claude mcp list` 로 등록 확인 → 세션 재시작. `.mcp.json` JSON 문법 오류도 흔한 원인이다 |
| 반환이 `BOARD_TOKEN 미설정` | env가 MCP 서버 프로세스에 전달되지 않음 | A안의 `${VAR}` 치환이 동작하지 않는 경우가 대부분. B안(`--env`)이나 C안(직접 지정 + gitignore 확인)으로 전환 |
| `[board] 401 ...` / `[board] 403 ...` | 토큰이 무효하거나 그 경로가 토큰 스코프 밖 | PAT 재발급 또는 스코프에 대상 보드 WRITE grant 추가 |
| `[board] 400 GET /api/agent/boards: 에이전트 토큰이 필요합니다.` | 토큰 없이(쿠키 세션으로) 에이전트 API 접근 | `BOARD_TOKEN` 을 설정한다 |
| 목록이 **빈 배열** | 이 토큰이 쓸 수 있는 보드가 하나도 없다 | 토큰 스코프에 WRITE grant를 추가한다. **쓰기 경로로 진행하지 않는다** |
| 목록에 대상 boardId가 **없다** | 그 토큰은 이 보드에 쓸 권한이 없다 (다른 org PAT일 가능성) | 목록에 있는 보드 중에서 고르거나, 올바른 org PAT로 **MCP를 재등록**한다. **여기서 멈춘다** — 이 상태로 진행하면 테넌트 오등록이다 |
| 연결은 되는데 `baseUrl` 이 localhost | 로컬 개발 서버를 보고 있다 | 의도한 것이면 그대로. 프로덕션 등록이 목적이면 `BOARD_BASE_URL=https://tavlet.io` 로 고친다 |

**어떤 경우에도 REST를 직접 호출하거나 우회 스크립트를 만들지 않는다.** 그것은 승인 게이트를 우회하는 두 번째 쓰기 경로다.

---

## 6. 스킬 배포 (심링크)

정본은 이 저장소 안의 스킬 폴더다. `~/.claude/` 에는 **복사본이 아니라 심링크**를 둔다 — 복사본은 정본과 조용히 갈라진다.

```bash
ln -s "<WORKSPACE>/claude-utils/claude-skills/tavlet-tracker" \
      ~/.claude/skills/tavlet-tracker

ln -s "<WORKSPACE>/claude-utils/claude-skills/tavlet-tracker/commands/tvl.md" \
      ~/.claude/commands/tvl.md
```

확인:

```bash
ls -l ~/.claude/skills/tavlet-tracker ~/.claude/commands/tvl.md
```

두 심링크가 정본 경로를 가리키면 배포 완료다. 이후 `/tvl` 슬래시 커맨드와 스킬 자동 활성화가 모두 동작한다.

> 목적지 저장소(`claude-utils/claude-skills`)는 git 저장소가 아니므로 워크트리 격리를 쓸 수 없다. 산출물을 해당 경로에 직접 생성한다.
