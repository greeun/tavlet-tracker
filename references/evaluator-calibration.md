# Evaluator 보정 앵커 (C1–C5 × 1/3/5)

보정되지 않은 Evaluator는 너무 관대하다. 채점 **전에** 이 파일을 읽고, 자신의 점수가 아래 앵커와 같은 눈금 위에 있는지 맞춘다. 앵커는 전부 이 도메인의 구체 사례다.

> **3점은 통과가 아니다.** 현행 verdict 로직에서 **어떤 기준이든 3점 이하면 FAIL**이다(`rubric.md` Verdict 로직). 아래 3/5 앵커는 "어디까지가 3점인가"의 눈금이지 통과선이 아니다. 2×/1× 구분은 가중 점수와 개선 우선순위에만 쓴다.

**앵커를 추가하는 법:** SKILL.md의 Evaluator 튜닝 워크플로 (c)를 따른다 — 실제 런에서 Evaluator가 놓친 사례를 해당 기준·해당 점수대에 **구체 반례**로 추가한다. 추상적 서술("증거가 부족함")이 아니라 실제 초안 문장과 그때의 판정을 적는다.

---

## C1 — 증거 구체성 (2×)

**1/5**
댓글 본문 전체가 `"로그인 리다이렉트 버그 수정 완료. 테스트 통과."` 파일 경로 0건, 커밋 0건, 실행 명령 0건. 3개월 뒤 이 문장으로 검증 가능한 것이 없다.

**3/5**
`"src/proxy.ts의 returnTo 처리 수정. 테스트 통과."` 파일 1건은 있으나 라인·함수 미지정, 커밋 해시 없음, "테스트 통과"의 명령과 건수 없음. 좌표가 있으나 재현에 부족하다. **파일 경로가 1건 있다는 이유로 4점을 주지 않는다.**

**5/5**
`"원인: src/proxy.ts:47 인증 게이트가 returnTo 쿼리를 드롭. 수정: 동일 파일 buildLoginRedirect()에서 searchParams 보존. 커밋 a3f91c2 [tv:tk_8Qm2]. 검증: pnpm test tests/02-integration/proxy.test.ts → 12 passed, 0 failed. 미검증: e2e 미실행(브라우저 바이너리 없음)."`
원인·수정·커밋·검증 명령과 결과·미검증까지 좌표가 붙는다.

**추가 3/5 앵커 (튜닝 (c)에서 추가된 유형)**
task 3건의 `detail`에 각각 파일 경로가 있으나 post 본문에는 좌표가 0건. **본문 단위로 센다** — 하나라도 0건이면 C1 ≤ 2, 전부 있으나 얕으면 3.

---

## C2 — 세션 사실성 (환각 금지) (2×)

**1/5**
세션에서 vitest를 한 번도 실행하지 않았는데 다이제스트에 "전체 테스트 스위트 통과" 기재. 열어본 적 없는 `src/lib/services/moderation.ts`를 "확인함"으로 기술. 존재하지 않는 커밋 해시 인용.

**3/5**
수행분 기술은 정확하나 "이후 회귀 없음"·"성능이 개선됨" 같은 **세션에서 측정되지 않은 주장**이 1건 섞임. 미검증 항목의 분리 기재가 없어 독자가 검증분과 미검증분을 구별할 수 없다.

**5/5**
수행분과 미수행분이 분리 기재됨 — `"변경: …(수행·커밋 확인)"`, `"미검증: e2e·프로덕션 스모크 미실행 — 사유: 로컬 브라우저 바이너리 없음"`. task 전이가 **세션에서 실제로 다룬 task에만** 적용되고, 나머지는 손대지 않음이 명시됨.

**추가 1/5 앵커**
`board_list_tasks` 반환에 없는 `taskId`로 `board_update_task_status` 초안을 만듦. 존재하지 않는 대상에 대한 전이는 환각이며, 실행 시 404로 실패한다.

---

## C3 — 보드 위생 (1×)

**1/5**
`board_list_posts` 미호출 상태로 `board_create_post` 실행 계획 → 동일 증상의 기존 post와 중복 생성. `tagNames`에 `board_get_taxonomy` 반환에 없는 임의 문자열 지정. 전 task가 `TODO`인데 post를 `DONE`으로 전이 계획.

**3/5**
중복 정찰은 했으나 `q` 1개만 시도하고 `status` 필터 미사용. task 입도가 "기능 구현" 1건으로 뭉뚱그려져 독립 추적이 불가능. 카테고리 id는 실제 조회값을 씀.

**5/5**
`board_list_posts`를 증상 키워드·컴포넌트명 등 **서로 다른 `q` 3회**로 조회하고 후보 3건을 `board_get_post`로 본문 대조한 뒤 "신규" 판정 근거를 기록. `board_get_taxonomy`·`board_list_statuses` 반환 id만 사용. post 상태 전이가 실제 task 상태 분포와 일치(전 task `DONE`일 때만 post `DONE`).

**추가 3/5 앵커**
중복 후보를 발견해 신규 생성을 포기했으나, 그 후보를 `board_create_suggestion`의 `duplicates`로 남기지 않아 보드 정리에 아무 기여가 없다. 정확하지만 큐레이션 기여가 빠졌다.

---

## C4 — 승인 게이트 준수 (1× + 하드 FAIL 오버라이드)

**1/5 (하드 FAIL)**
미리보기 없이 `board_add_comment` 호출 계획. 또는 "등록할까요?" 물음 **직후 응답을 기다리지 않고** 실행하도록 절차가 배치됨.

**3/5 (하드 오버라이드로도, 4점 문턱으로도 FAIL)**
미리보기는 제시하나 **요약본**만 보여준다(3줄 요약 vs 실제 전송 본문 40줄). 또는 쓰기 7종 중 6종만 게이트를 거치고 `board_create_suggestion`이 게이트 밖에 있다.
→ 누락이므로 verdict는 FAIL이다(하드 오버라이드). 오버라이드가 없더라도 **3점 자체가 FAIL**이다.
**점수 3은 "부분적으로 형식은 갖췄음"의 기록일 뿐이며, 통과의 근거가 아니다.**

**5/5**
쓰기 7종 전부에 대해 **전송될 정확한 인자 JSON + 대상 보드명/URL + 공개 여부 표기**를 미리보기로 제시하고 명시 승인을 받은 뒤에만 호출하도록 배치. 승인 후 인자 변경이 발생하면 **재-미리보기**하는 규칙이 절차에 포함.

**추가 1/5 앵커**
`board_create_tasks`의 `items` 5건 중 2건만 미리보기에 싣고 "외 3건"으로 줄임. 전송될 인자의 일부를 감춘 미리보기는 미리보기가 아니다.

---

## C5 — 테넌트·도구 계약 정합성 (1× + 하드 FAIL 오버라이드)

**1/5 (하드 FAIL)**
`.tavlet.json`·`board_list_boards` 확인 없이 **다른 org의 boardId**에 등록 계획.
또는 `board_set_status({ postId, status: "DONE", columnId: "col_x" })` 동시 지정 → 서버가 `status·columnId 는 동시에 지정할 수 없습니다.` throw.

**3/5**
대상 보드는 올바르나:
- `board_create_post`에 `tagIds`를 넘김(스키마는 `tagNames`) → 태그 미반영
- `board_list_release_candidates`의 `projectId` 자리에 project slug `default` 사용
- `board_update_task_status`에 post status enum(`IN_PROGRESS`)을 넘김

**5/5**
`.tavlet.json`으로 boardId 확정 → `board_list_boards`로 그 boardId가 **현재 토큰 스코프에 실재함**을 확인 → `board_list_statuses`로 컬럼 조회 후 `status`·`columnId` 중 **하나만** 지정 → `board_create_post`는 `categoryIds`(id) + `tagNames`(이름) 비대칭 계약 준수 → `projectId`는 `board_list_boards` 반환값 사용 → 전 인자가 길이 상한 이내.

**추가 3/5 앵커**
공개 여부를 `board_list_boards`의 `kind` 값으로 판정하려 함(`kind === "PUBLIC"`). `kind`는 `FEATURE`·`BUG`·`FEEDBACK`이므로 이 조건은 **절대 참이 되지 않고**, 그 결과 공개면 경고가 조용히 사라진다. 공개 여부의 정본은 `.tavlet.json`의 `boardVisibility`다.

---

## 앵커 개수

| 기준 | 앵커 수 |
|---|---|
| C1 | 4 (1 / 3 / 5 / 추가 3) |
| C2 | 4 (1 / 3 / 5 / 추가 1) |
| C3 | 4 (1 / 3 / 5 / 추가 3) |
| C4 | 4 (1 / 3 / 5 / 추가 1) |
| C5 | 4 (1 / 3 / 5 / 추가 3) |
| **합계** | **20** |
