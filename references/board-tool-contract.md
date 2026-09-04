# board_* 도구 정본 계약 (14종)

`tavlet-tracker`의 Planner · Generator · Evaluator · 오케스트레이터가 **모두** 이 파일을 읽는다. 도구 계약의 유일한 정본이다 — 다른 파일에 복사하지 않는다.

모든 값은 tavlet 체크아웃의 실제 소스에서 확인된 것이다. 근거 경로는 tavlet 레포 루트 기준.

- 도구 등록(원격, 정규 경로): `src/lib/mcp/board-tools.ts` · 엔드포인트 `src/app/api/mcp/route.ts`
- 도구 등록(로컬 stdio, 개발용): `agent/mcp/board/server.ts` + REST 클라이언트 `board-client.ts`
- 검증 스키마: `src/lib/validation/posts.ts` · `post-tasks.ts` · `releases.ts` · `primitives.ts`
- 보드 목록 DTO: `src/lib/services/agent-boards.ts`

> tavlet `CLAUDE.md`는 MCP 도구를 "12종"으로 기재하지만 `server.ts`의 `registerTool` 호출은 **14개**다. **코드를 따른다.**

---

## 0. 성공/실패 판정 — 가장 흔한 함정

두 구현 모두 **오류를 예외로 전파하지 않는다.** 도구 결과 안에 담아 되돌린다:

```ts
// 원격(board-tools.ts) — REST 와 같은 오류 봉투
{ content: [{ type: "text", text: '{"ok":false,"error":"…","code":"…"}' }], isError: true }

// 로컬 stdio(server.ts:9-16) — 예외 문자열 그대로
catch (e) { return { content: [{ type: "text", text: String(e) }], isError: true }; }
```

**따라서 도구가 텍스트를 되돌렸다는 사실만으로 성공으로 판단하면 안 된다.**

**판정 규칙:**
- 반환에 `isError: true` 가 있으면 → **실패** (양쪽 공통, 가장 확실한 신호)
- 파싱한 JSON이 `{"ok": false, …}` 이면 → **실패** (원격)
- 반환 텍스트가 `Error:` 로 시작하면 → **실패** (stdio)
- 반환 텍스트가 `[board] <숫자 status> <METHOD> <path>: <본문 앞 300자>` 패턴을 포함하면 → **실패** (stdio, 근거: `board-client.ts:20`)
- 그 외에는 JSON 문자열이며 성공

**실패 시:** 반환 원문을 **그대로** 표면화하고 후속 쓰기를 **취소**한다. 이미 실행된 쓰기와 취소된 쓰기를 분리해 보고한다.

**전역 실패 모드:**
| 증상 | 경로 | 원인 |
|---|---|---|
| HTTP 401 `{"success":false,"error":{"code":40101,…}}` | 원격 | Authorization 헤더가 없다 |
| HTTP 401 `AGENT_TOKEN_REQUIRED` | 원격 | 인증은 됐지만 PAT 가 아니다(쿠키 세션) — MCP는 에이전트 토큰 전용 표면이다 |
| HTTP 401 `INVALID_API_TOKEN` | 원격 | PAT 가 무효(폐기·오타) |
| `{"ok":false,…,"code":"TOKEN_SCOPE_DENIED"}` (403) | 원격 | 대상이 토큰 스코프 밖. 조회 도구는 READ, 쓰기 도구는 WRITE grant 를 요구한다 |
| `BOARD_TOKEN 미설정` | stdio | env `BOARD_TOKEN`이 MCP 서버 프로세스에 전달되지 않음 (`board-client.ts:9-10`) |
| `[board] 400 GET /api/agent/boards: 에이전트 토큰이 필요합니다.` | stdio | 토큰 없이(쿠키 세션으로) 에이전트 API 접근 (`agent-boards.ts:26`) |

---

## 1. 인증 · 환경변수

**원격(정규 경로)** — env 없음. PAT 를 `Authorization: Bearer` 헤더로 넘긴다. 대상 테넌트는 **토큰 스코프만이** 정하며, 서버가 기본 보드를 고르는 경로는 존재하지 않는다 — `board_create_post` 의 `boardId` 는 필수 인자다.

**로컬 stdio(개발용)** — env 3종:

| 변수 | 기본값 | 역할 | 근거 |
|---|---|---|---|
| `BOARD_BASE_URL` | `http://localhost:18000` | REST 베이스. 뒤 슬래시는 제거됨 | `board-client.ts:4` |
| `BOARD_TOKEN` | 없음 | PAT. **미설정이면 모든 호출이 throw** | `board-client.ts:5,10` |
| `BOARD_DEFAULT_BOARD_ID` | 없음 | `board_create_post`에서 `boardId` 생략 시 대체 — **이 스킬은 쓰지 않는다**(게이트 G3) | `server.ts:46` |

PAT 접두사: 신규 발급은 `tvl_`, 레거시 `hhb_`는 **검증 수용 전용**(신규 발급 없음). 두 접두사 모두 **스크럽 대상**이다.

---

## 2. 테넌시 · URL 규약

`board_list_boards` 반환 형태 (근거: `agent-boards.ts:7-17,45-54`):

```jsonc
{ "boards": [ {
    "boardId": "<boardId>",
    "projectId": "<DB id>",              // ← 릴리스 도구의 projectId 인자는 여기서 해소한다
    "kind": "FEATURE",                   // FEATURE | BUG | FEEDBACK — 공개 여부가 아니다
    "name": "<보드명>",
    "org":       { "slug": "<org-slug>",       "name": "..." },
    "workspace": { "slug": "<workspace-slug>", "name": "..." },
    "project":   { "slug": "<project-slug>",   "name": "..." },
    "url": "/o/{orgSlug}/{wsSlug}/{projSlug}/{boardId}"
} ] }
```

- 이 목록은 **현재 토큰의 WRITE grant가 커버하는 보드만** 담는다 (`agent-boards.ts:37-44`). **목록에 없는 boardId는 그 토큰으로 쓸 수 없다.** 테넌트 확인의 정본 수단이다.
- 보드 피드 URL: `/o/{orgSlug}/{wsSlug}/{projSlug}/{boardId}` — 마지막 세그먼트가 **boardId**
- post URL: `/o/{orgSlug}/{wsSlug}/{projSlug}/{boardId}/post/{postId}` — 마지막 세그먼트가 **postId**
- 커밋 트레일러: 이 스킬은 특정 트레일러 형식을 **요구하지 않는다.** 구 `[tv:<taskId>]` 규약은 tavlet 레포의 S0~S4 파이프라인과 공존하기 위한 것이었고, 그 파이프라인은 삭제됐다(tavlet `ff3fa1f`). 대상 레포에 자체 규약이 있으면 그것을 따른다.

### 대상 테넌트 — 하드코딩하지 않는다

이 스킬은 tavlet.io 의 **모든 org**에서 동작한다. 특정 org의 boardId·slug 를 이 파일에 적어 두지 않는다 — 그 값은 실행 환경마다 다르고, 적어 두면 다른 테넌트에서 조용히 틀린 보드를 가리키게 된다.

| 무엇 | 어디서 온다 |
|---|---|
| `baseUrl` · `org` · `workspace` · `project` · `boardId` · `boardVisibility` | 대상 레포의 `.tavlet.json` (스키마: `mcp-setup.md` §3) |
| 그 boardId 가 실재하는지 | 매 실행 `board_list_boards()` 반환과 대조 (게이트 **G3**) |
| 공개면 여부 | `.tavlet.json` 의 `boardVisibility` 선언 — 어떤 도구도 반환하지 않는다(아래 §가시성) |

`.tavlet.json` 이 없으면 사용자에게 묻고, `board_list_boards()` 로 실재를 확인한 뒤 생성을 제안한다. **추측한 boardId 로 쓰기를 진행하지 않는다.**

### §가시성 — 어떤 도구도 공개 여부를 반환하지 않는다

DB 상 보드는 `kind`(`BoardKind` = `FEATURE`·`BUG`·`FEEDBACK`)와 `visibility`(`Visibility` = `PUBLIC`·`PRIVATE`·`INTERNAL`, 기본 `PUBLIC`)를 **따로** 가진다 (근거: `prisma/schema.prisma:282-283`, `138-142`; `src/lib/validation/primitives.ts:23`). 그런데 `AgentBoardDTO`는 `kind`만 싣고 **`visibility`는 싣지 않는다** (`agent-boards.ts:7-17`).

**결론 — 반드시 지킬 것:**
- `board_list_boards`의 `kind` 값을 공개 여부 판정에 쓰지 않는다. `kind === "PUBLIC"` 은 **절대 참이 되지 않는 조건**이다.
- 공개 여부의 정본은 `.tavlet.json`의 **`boardVisibility`** (`PUBLIC` | `INTERNAL` | `PRIVATE`) 이며, 이는 운영자가 선언하는 값이다.
- 값이 없거나 모호하면 **`PUBLIC`으로 간주(안전 측 기본값)** 하고 사용자에게 확인한다. DB 기본값도 `PUBLIC`이다.

---

## 3. 도구 14종 계약표

**R = 읽기(7종, 게이트 없음) · W = 쓰기(7종, 미리보기 + 명시 승인 필수).** 스테이지 코드는 오케스트레이터 워크플로 단계다.

| # | 도구 | R/W | 스테이지 | 인자 계약 | 실패 모드 | 사후 read-back 수단 |
|---|---|---|---|---|---|---|
| 1 | `board_list_boards` | R | **SA 테넌트 해소** (G3) | 인자 없음 (`{}`) | 토큰 미설정 → `BOARD_TOKEN 미설정`. 토큰 없이 쿠키 세션 → 400 `에이전트 토큰이 필요합니다.` **빈 목록 = 이 토큰이 쓸 수 있는 보드 없음 → 중단** | — |
| 2 | `board_list_posts` | R | **SB 중복 정찰** (G4, 필수 선행) | `{ boardId, status?, q? }` — `boardId` 필수 | `boardId` 누락 → 스키마 오류. 결과 0건이 "중복 없음"의 근거가 되려면 **서로 다른 `q` 2회 이상** 필요 | — |
| 3 | `board_get_post` | R | **SB 중복 정찰 / SG 현황 조회** | `{ postId }` | 404(없음)·403(스코프 밖) → 원문 표면화 후 중단 | — |
| 4 | `board_get_taxonomy` | R | **SC 분류 어휘 확인** | `{ boardId }` | 반환의 **실제 id만** 사용. 존재하지 않는 카테고리 id를 `board_create_post`에 넘기면 서비스가 거절 | — |
| 5 | `board_list_statuses` | R | **SD 상태 어휘 확인** (`board_set_status` 선행) | `{ boardId }` | `board_set_status`의 `columnId` 후보는 **여기서만** 얻는다. 조회 없이 `columnId`를 지어내지 않는다 | — |
| 6 | `board_list_tasks` | R | **SF/SG task 현황** | `{ postId }` | post가 없거나 스코프 밖이면 원문 표면화 후 중단 | — |
| 7 | `board_list_release_candidates` | R | **SK 릴리스 초안 후보** | `{ projectId }` ← `board_list_boards`의 `projectId`. **project slug 금지** | 프로젝트 내 DONE·릴리스 미할당 post 목록 반환. slug를 넘기면 결과 없음/오류 | — |
| 8 | **`board_create_post`** | **W** | **SE post 등록** | `{ title, body, boardId?, categoryIds?, tagNames? }`. `boardId` 생략 시 `BOARD_DEFAULT_BOARD_ID` env 사용. **`categoryIds`는 id 배열, `tagNames`는 이름 배열 — 비대칭** | `boardId` 미지정 & env 미설정 → throw `boardId 미지정 & BOARD_DEFAULT_BOARD_ID 미설정 — board_list_boards로 등록 대상 boardId를 먼저 확인하세요.` 길이 초과 → 검증 오류 | **가능** — `board_get_post({postId})` 로 `title`·`body`·`categoryIds`·`tags` 대조 |
| 9 | **`board_create_tasks`** | **W** | **SF task 분해** | `{ postId, items: [{ title, detail? }] }` (일괄). `items` **1–50개** | 빈 `items` 등록 금지(빈 등록은 절차상 중단). 51개 이상 → 검증 오류 | **가능** — `board_list_tasks({postId})` 로 등록된 항목 대조 |
| 10 | **`board_update_task_status`** | **W** | **SG 진행 갱신** | `{ postId, taskId, status }`, status ∈ **`TODO`·`DOING`·`DONE`·`DROPPED`** | **post 상태 enum과 다른 집합이다 — 혼동 금지.** 세션에서 다루지 않은 task는 전이하지 않는다 | **가능** — `board_list_tasks({postId})` 로 해당 task 의 status 대조 |
| 11 | **`board_add_comment`** | **W** | **SH 세션 다이제스트** | `{ postId, body }` — body **1–5000자** | **`internal` 플래그 없음 = 공개 댓글.** 스크럽(G7) 필수 | **부분** — `board_get_post({postId})` 의 `commentCount` 증가만 확인. **본문은 재조회되지 않는다**(근거: `posts.ts:340` — DTO에 댓글 본문 없음) |
| 12 | **`board_set_status`** | **W** | **SI 상태 전이** | `{ postId, status? , columnId? }`, status ∈ **`OPEN`·`UNDER_REVIEW`·`PLANNED`·`IN_PROGRESS`·`DONE`·`DECLINED`** | **둘 다 없음 → throw `status 또는 columnId 중 하나는 필수입니다.` 둘 다 지정 → throw `status·columnId 는 동시에 지정할 수 없습니다.`** (근거: `server.ts:159-160`) | **가능** — `board_get_post({postId})` 의 `status`(=`boardStatus.kind`) · `boardStatus.id`(=`columnId`) 대조 (근거: `posts.ts:335,349`) |
| 13 | **`board_create_suggestion`** | **W** | **SJ 분류·중복 제안** | `{ postId, categoryIds?, tagIds?, kindNote?, priority?, rationale, duplicates? }`. `rationale` **필수**. `duplicates` 항목 = `{ candidateId, confidence, reason }`. `priority`·`confidence` ∈ `HIGH`·`MEDIUM`·`LOW` | **여기서는 `tagIds`(id) — `board_create_post`의 `tagNames`(이름)와 반대다.** `rationale` 누락 → 스키마 오류. **`categoryIds`·`tagIds` 중 최소 하나가 있어야 한다** — 둘 다 비우면 `rationale` 이 있어도 `{"ok":false,"error":"올바르지 않은 제안입니다.","code":"VALIDATION_FAILED"}` 로 거절된다(2026-09-04 실측). 분류할 대상이 없는 제안은 성립하지 않기 때문이다. 병합은 항상 사람 승인 | **계약 14종에는 없으나 `board_get_suggestion` 이 실재한다**(아래 §3-1 주석). 14종만 쓴다면 **반환 id만 보고** |
| 14 | **`board_create_release_draft`** | **W** | **SK 릴리스 초안** | `{ projectId, version, name?, body, entries }`. `entries` 항목 = `{ title, body, type, postIds }`, `postIds` **1개 이상**. `type` ∈ `NEW`·`IMPROVED`·`FIXED`·`BETA` | **version 중복 → 409.** 발행되지 않는 **초안**임을 미리보기에 명시 | **초안 자체 없음** — 반환 id·version 그대로 보고. 간접 확인 2종만: `board_get_post({postId}).affectedRelease` 대조 · `board_list_release_candidates` 에서 해당 post 소거 |

**쓰기 7종 = 8·9·10·11·12·13·14.** `board_create_suggestion`은 REST `POST /api/agent/posts/{postId}/suggestions`이며 보드에 상태를 남기므로 **게이트 대상이다.**
**읽기 7종 = 1·2·3·4·5·6·7.** Evaluator는 읽기 7종만 호출할 수 있다.

### §3-1 사후 read-back — 쓰기 7종 중 5종만 검증된다

실행(12단계) 후의 read-back은 **읽기 7종으로 할 수 있는 것까지만** 가능하다. 도구 목록에 없는 조회는 존재하지 않는다.

| 쓰기 도구 | read-back | 무엇을 대조하나 | 근거 |
|---|---|---|---|
| `board_create_post` | 가능 | `board_get_post` 의 `title`·`body`·`categoryIds`·`tags` | `services/posts.ts:334-341` |
| `board_create_tasks` | 가능 | `board_list_tasks` 의 항목 목록 | `board-client.ts:53` |
| `board_update_task_status` | 가능 | `board_list_tasks` 의 해당 task status | `board-client.ts:53` |
| `board_add_comment` | **부분** | `board_get_post` 의 `commentCount` 증가만. **본문 대조 불가** | `services/posts.ts:340` (DTO에 댓글 본문 없음) |
| `board_set_status` | 가능 | `board_get_post` 의 `status`·`boardStatus.id` | `services/posts.ts:335,349` |
| `board_create_suggestion` | **14종 안에는 없음** | — 계약이 정한 14종에 조회 도구가 없다. 다만 원격 서버는 `board_get_suggestion({postId})` 를 노출하며(2026-09-04 실측 18종), 그것을 쓰면 `{"suggestion":null}` 로 미등록을 실증할 수 있다 | `server.ts` `registerTool` 14건 전수 — suggestion 조회 도구 부재. 원격은 그보다 많다 |
| `board_create_release_draft` | **초안 자체 없음** | 간접 2종만: 포함된 post 의 `affectedRelease`(version 대조) · `board_list_release_candidates` 에서 그 post 소거 | `services/posts.ts:346` · `services/releases.ts:399`(후보 조건 `affectedReleaseId: null`) · `releases.ts:462-463`(초안 생성이 `affectedReleaseId` 를 채운다) |

**보고 규약 (지키지 않으면 C2 위반):**
- read-back이 **없는 2종**(`board_create_suggestion`·`board_create_release_draft`)은 **미리보기와 최종 보고 양쪽에** `반환 id만 · 재조회 수단 없음` 을 표기한다.
  - 다만 이 표기는 **계약 14종 기준**이다. 세션에 `board_get_suggestion` 이 노출되어 있다면 그것으로 확인할 수 있고, 확인했다면 표기 대신 그 결과를 적는다. 없는 확인을 했다고 적지 않는 것이 규칙의 취지이지, 있는 도구를 쓰지 말라는 뜻이 아니다.
- `board_add_comment`는 "댓글 등록을 확인했다"가 아니라 **"`commentCount` 증가만 확인, 본문은 재조회 불가"** 로 적는다.
- 릴리스 초안의 간접 확인 2종을 수행했다면 **간접임을 명시**한다. 초안 본문·엔트리는 어느 쪽으로도 재조회되지 않는다.
- **검증하지 않은 것을 검증했다고 쓰지 않는다.** 이 스킬은 그 문장을 막으려고 존재한다.

---

## 4. 필드 길이 상한

| 대상 | 상한 | 근거 |
|---|---|---|
| post `title` | 1–200자 | `posts.ts:7` |
| post `body` | 1–10000자 | `posts.ts:8` |
| post `tagNames` | 항목당 1–40자, **최대 10개** | `posts.ts:10` |
| task `title` | 1–200자 | `post-tasks.ts:8` |
| task `detail` | ≤2000자 | `post-tasks.ts:9` |
| task `items` 배열 | **1–50개** | `post-tasks.ts:12-13` |
| comment `body` | 1–**5000**자 | `posts.ts:44` |
| release `version` | 1–50자(trim, 공백만 금지) | `releases.ts:29-33` |
| release `name` | ≤100자 | `releases.ts:76` |
| release draft `body` | 1–10000자 | `releases.ts:77` |
| release `entries` 배열 | **1–50개** | `releases.ts:78` |
| release entry `title` | 1–200자 | `releases.ts:68` |
| release entry `body` | 1–**20000**자 | `releases.ts:69` |
| release entry `postIds` | **1–100개** | `releases.ts:71` |

> **기존 스킬 문서와의 불일치 — 코드를 따른다.** tavlet 레포의 `agent/skills/tavlet-board-result/SKILL.md:29`는 댓글 본문을 "≤10000자"로 기재하지만 실제 검증 스키마는 **5000자**다(`posts.ts:44`). `tavlet-tracker`는 **5000자**를 쓴다. 기존 스킬 문서의 숫자를 복사하지 않는다.

---

## 5. enum 정본

| 대상 | 허용 값 | 근거 |
|---|---|---|
| **task status** (`board_update_task_status`) | `TODO` · `DOING` · `DONE` · `DROPPED` | `server.ts:125`, `post-tasks.ts:19` |
| **post status** (`board_set_status`) | `OPEN` · `UNDER_REVIEW` · `PLANNED` · `IN_PROGRESS` · `DONE` · `DECLINED` | `server.ts:153`, `primitives.ts:24-31` |
| **suggestion priority / duplicate confidence** | `HIGH` · `MEDIUM` · `LOW` | `server.ts:80,83` |
| **changelog entry type** | `NEW` · `IMPROVED` · `FIXED` · `BETA` | `server.ts:187`, `releases.ts:4` |
| **board kind** (`board_list_boards.kind`) | `FEATURE` · `BUG` · `FEEDBACK` | `prisma/schema.prisma:138-142` |
| **board visibility** (도구 미노출) | `PUBLIC` · `PRIVATE` · `INTERNAL` | `primitives.ts:23`, `prisma/schema.prisma:132-136,283` |

**두 status 집합은 교집합이 `DONE` 하나뿐이다.** `IN_PROGRESS`를 task에 넘기거나 `DOING`을 post에 넘기면 스키마 오류다.

---

## 6. 비대칭·혼동 체크리스트 (인자 확정 전 매번 대조)

- [ ] `board_create_post` → **`tagNames`**(태그 **이름** 배열, 항목 40자·최대 10개) · `categoryIds`(**id** 배열)
- [ ] `board_create_suggestion` → **`tagIds`**(태그 **id** 배열) · `categoryIds`(id 배열) — `create_post`와 반대다
- [ ] `board_create_suggestion` → 두 배열이 **모두 비어 있지 않은지**. 대상 보드의 `board_get_taxonomy` 가 `{"categories":[],"tags":[]}` 라면 지정할 id 가 없으므로 **이 쓰기 자체를 계획에서 뺀다.** 어휘를 만드는 도구는 14종에 없어 사람이 콘솔에서 먼저 만들어야 한다
- [ ] `projectId`는 **DB id**다. `board_list_boards` 반환의 `projectId`를 쓴다. project **slug**(`default`)를 넣지 않는다
- [ ] `board_set_status`는 `status`와 `columnId` 중 **정확히 하나**. 둘 다 없거나 둘 다 있으면 throw
- [ ] `columnId` 값은 `board_list_statuses` 반환에서만 가져온다
- [ ] `categoryIds`·`tagIds` 값은 `board_get_taxonomy` 반환에서만 가져온다
- [ ] task status vs post status 집합 혼동 없음
- [ ] 대상 `boardId`가 `board_list_boards` 반환에 실재
- [ ] 모든 문자열이 §4 길이 상한 이내
- [ ] `board_add_comment`는 팀 전용 플래그가 없다 — 이 댓글은 **공개**다

---

## 7. 워크플로 스테이지 요약

```
SA 테넌트 해소      board_list_boards
SB 중복 정찰        board_list_posts (q 2회 이상) → board_get_post
SC 분류 어휘        board_get_taxonomy
SD 상태 어휘        board_list_statuses
SE post 등록        board_create_post            [W]
SF task 분해        board_list_tasks → board_create_tasks   [W]
SG 진행 갱신        board_list_tasks → board_update_task_status  [W]
SH 세션 다이제스트  board_add_comment            [W]  (공개 댓글)
SI 상태 전이        board_list_statuses → board_set_status  [W]
SJ 분류·중복 제안   board_get_taxonomy → board_create_suggestion  [W]
SK 릴리스 초안      board_list_release_candidates → board_create_release_draft  [W]
```

**의존 순서:** SE → SF → SG → SH → SI. SJ는 대상 post가 존재한 뒤. SK는 관련 post가 `DONE`이 된 뒤.
