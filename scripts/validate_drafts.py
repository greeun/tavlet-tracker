#!/usr/bin/env python3
"""drafts_v<n>.md 결정론적 검증기 — tavlet-tracker.

읽기 전용이다. board_* 도구를 호출하지 않고 네트워크에 접속하지 않는다.
승인 게이트(G5)를 우회하는 두 번째 쓰기 경로가 아니다 — 초안 텍스트만 읽고 판정한다.

정본 계약: references/board-tool-contract.md §3 · §4 · §5 · §6
루브릭 대응: C1(증거 좌표) · C5(도구 계약) · G7(스크럽)

사용:
    python3 scripts/validate_drafts.py <RUN_DIR>/drafts_v<n>.md
    python3 scripts/validate_drafts.py <path> --json

종료 코드:
    0 = 지적 사항 없음
    1 = ERROR 1건 이상 (제출 금지)
    2 = 파싱 실패 · 사용법 오류
WARN 만 있으면 0 으로 끝나되 리포트에 남는다 — 사람이 판단할 항목이라는 뜻이다.
"""

import argparse
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------- 계약 상수
# 근거: references/board-tool-contract.md §5 enum 정본
TASK_STATUS = {"TODO", "DOING", "DONE", "DROPPED"}
POST_STATUS = {"OPEN", "UNDER_REVIEW", "PLANNED", "IN_PROGRESS", "DONE", "DECLINED"}
PRIORITY = {"HIGH", "MEDIUM", "LOW"}
ENTRY_TYPE = {"NEW", "IMPROVED", "FIXED", "BETA"}

WRITE_TOOLS = {
    "board_create_post",
    "board_create_tasks",
    "board_update_task_status",
    "board_add_comment",
    "board_set_status",
    "board_create_suggestion",
    "board_create_release_draft",
}
# read-back 수단이 없는 2종 — 초안에 표기 의무가 있다 (§3-1)
NO_READBACK = {"board_create_suggestion", "board_create_release_draft"}

# 근거: §4 필드 길이 상한
LIMITS = {
    "post_title": (1, 200),
    "post_body": (1, 10000),
    "tag_name": (1, 40),
    "task_title": (1, 200),
    "task_detail": (0, 2000),
    "comment_body": (1, 5000),
    "release_version": (1, 50),
    "release_name": (0, 100),
    "release_body": (1, 10000),
    "entry_title": (1, 200),
    "entry_body": (1, 20000),
}

# ---------------------------------------------------------------- 스크럽 패턴
# 근거: G7 · generator-prompt (e) · evaluator 누출 프로브
SECRET_PATTERNS = [
    (r"\btvl_[A-Za-z0-9_\-]{8,}", "tavlet PAT (tvl_ 접두사)"),
    (r"\bhhb_[A-Za-z0-9_\-]{8,}", "레거시 PAT (hhb_ 접두사)"),
    (r"(?i)\bbearer\s+[A-Za-z0-9._\-]{16,}", "Bearer 토큰"),
    (r"\bsk-[A-Za-z0-9]{16,}", "OpenAI 계열 API 키"),
    (r"\bAKIA[0-9A-Z]{16}\b", "AWS 액세스 키 ID"),
    (r"\bgh[pousr]_[A-Za-z0-9]{20,}", "GitHub 토큰"),
    (r"\bxox[abposr]-[A-Za-z0-9\-]{10,}", "Slack 토큰"),
    (r"(?i)\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp)://[^\s\"'<>]+",
     "커넥션 문자열"),
    (r"(?i)\b(?:DATABASE_URL|SECRET_KEY|PRIVATE_KEY|ACCESS_TOKEN|API_KEY|"
     r"CLIENT_SECRET|BOARD_TOKEN)\s*[=:]\s*\S+", ".env 값 대입"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "개인 키 블록"),
    (r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b", "이메일 주소"),
    (r"/Users/[A-Za-z0-9._\-]+/", "사용자 홈 절대경로 (macOS)"),
    (r"/home/[A-Za-z0-9._\-]+/", "사용자 홈 절대경로 (Linux)"),
    (r"[A-Za-z]:\\\\Users\\\\[A-Za-z0-9._\-]+\\\\", "사용자 홈 절대경로 (Windows)"),
]

# ---------------------------------------------------------------- 증거 좌표 패턴
# 근거: rubric.md C1 — 파일 경로 | 커밋 해시 | 명령+출력 | 에러 원문
COORD_PATTERNS = [
    (r"(?:[\w.\-]+/)+[\w.\-]+\.[A-Za-z0-9]{1,8}(?::\d+(?:-\d+)?)?", "파일 경로"),
    (r"\b[\w.\-]+\.[A-Za-z0-9]{1,8}:\d+(?:-\d+)?\b", "파일:라인"),
    (r"(?<![0-9a-zA-Z_])[0-9a-f]{7,40}(?![0-9a-zA-Z_])", "커밋 해시"),
    (r"```[\s\S]*?```", "명령/출력 블록"),
    (r"(?m)^\s*[$>#]\s+\S+", "셸 명령행"),
    (r"[A-Za-z_.]*(?:Error|Exception)\s*:", "에러 원문"),
    (r"Traceback \(most recent call last\)", "에러 원문"),
    (r"(?im)^\s*(?:error|fatal|panic)\s*:", "에러 원문"),
]

FIELD_LABELS = ["대상", "인자", "증거 출처", "선행 조건"]
NO_READBACK_MARK = "재조회 수단 없음"


class Finding:
    __slots__ = ("level", "where", "code", "message")

    def __init__(self, level, where, code, message):
        self.level = level          # ERROR | WARN
        self.where = where          # "쓰기 3 (board_add_comment)"
        self.code = code            # C5-ENUM 등
        self.message = message

    def as_dict(self):
        return {"level": self.level, "where": self.where,
                "code": self.code, "message": self.message}


# ---------------------------------------------------------------- 파싱
BLOCK_RE = re.compile(r"^##\s*쓰기\s*(\d+)\s*[:：]\s*(\S+)\s*$", re.M)


def parse_blocks(text):
    """drafts_v<n>.md 를 쓰기 블록 목록으로 자른다."""
    marks = list(BLOCK_RE.finditer(text))
    blocks = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        blocks.append({
            "no": m.group(1),
            "tool": m.group(2).strip("`*"),
            "body": text[m.end():end],
        })
    return blocks


def extract_args(block_body):
    """`- 인자:` 뒤의 JSON 을 뽑는다. 인라인·여러 줄·코드펜스 전부 허용."""
    m = re.search(r"^\s*[-*]\s*인자\s*[:：]", block_body, re.M)
    if not m:
        return None, "`- 인자:` 필드가 없다"
    tail = block_body[m.end():]
    tail = re.sub(r"^\s*```[a-zA-Z]*\s*", "", tail)
    start = tail.find("{")
    if start == -1:
        return None, "`- 인자:` 뒤에 JSON 객체가 없다"
    try:
        obj, _ = json.JSONDecoder().raw_decode(tail[start:])
    except ValueError as exc:
        return None, "인자 JSON 파싱 실패 — %s" % exc
    if not isinstance(obj, dict):
        return None, "인자가 JSON 객체가 아니다"
    return obj, None


# ---------------------------------------------------------------- 공통 검사기
def check_str(findings, where, value, key, limit_key, required=True):
    lo, hi = LIMITS[limit_key]
    if value is None:
        if required:
            findings.append(Finding("ERROR", where, "C5-REQUIRED",
                                    "필수 필드 `%s` 누락" % key))
        return
    if not isinstance(value, str):
        findings.append(Finding("ERROR", where, "C5-TYPE",
                                "`%s` 는 문자열이어야 한다 (현재 %s)"
                                % (key, type(value).__name__)))
        return
    n = len(value)
    if n < lo:
        findings.append(Finding("ERROR", where, "C5-LENGTH",
                                "`%s` 길이 %d — 하한 %d 미만" % (key, n, lo)))
    if n > hi:
        findings.append(Finding("ERROR", where, "C5-LENGTH",
                                "`%s` 길이 %d — 상한 %d 초과 (§4)" % (key, n, hi)))


def check_list(findings, where, value, key, lo, hi, required=True):
    if value is None:
        if required:
            findings.append(Finding("ERROR", where, "C5-REQUIRED",
                                    "필수 필드 `%s` 누락" % key))
        return False
    if not isinstance(value, list):
        findings.append(Finding("ERROR", where, "C5-TYPE",
                                "`%s` 는 배열이어야 한다" % key))
        return False
    if not (lo <= len(value) <= hi):
        findings.append(Finding("ERROR", where, "C5-LENGTH",
                                "`%s` 항목 %d개 — 허용 %d–%d개 (§4)"
                                % (key, len(value), lo, hi)))
        return False
    return True


def check_enum(findings, where, value, key, allowed, other_set=None, other_name=""):
    if value is None:
        return
    if value in allowed:
        return
    if other_set and value in other_set:
        findings.append(Finding("ERROR", where, "C5-ENUM-CROSS",
                                "`%s` = `%s` 는 %s 집합의 값이다 — 두 집합의 "
                                "교집합은 `DONE` 하나뿐이다 (§5)"
                                % (key, value, other_name)))
        return
    findings.append(Finding("ERROR", where, "C5-ENUM",
                            "`%s` = `%s` 는 허용 값이 아니다. 허용: %s"
                            % (key, value, " · ".join(sorted(allowed)))))


def check_project_id(findings, where, value):
    if value is None:
        findings.append(Finding("ERROR", where, "C5-REQUIRED",
                                "필수 필드 `projectId` 누락"))
        return
    if not isinstance(value, str):
        findings.append(Finding("ERROR", where, "C5-TYPE",
                                "`projectId` 는 문자열이어야 한다"))
        return
    # §6 — projectId 는 board_list_boards 반환의 DB id. project slug 금지.
    if value == "default" or re.fullmatch(r"[a-z][a-z0-9\-]{0,15}", value):
        findings.append(Finding("ERROR", where, "C5-SLUG",
                                "`projectId` = `%s` 가 project **slug** 로 보인다. "
                                "board_list_boards 반환의 DB id 를 쓴다 (§6)" % value))


def forbid_key(findings, where, args, key, hint):
    if key in args:
        findings.append(Finding("ERROR", where, "C5-ASYMMETRY",
                                "`%s` 를 넘겼다 — %s (§6)" % (key, hint)))


# ---------------------------------------------------------------- 도구별 검사
def validate_create_post(findings, where, args, bodies):
    check_str(findings, where, args.get("title"), "title", "post_title")
    check_str(findings, where, args.get("body"), "body", "post_body")
    bodies.append(("post body", args.get("body")))
    if "boardId" not in args:
        findings.append(Finding("ERROR", where, "C5-TENANT",
                                "`boardId` 미지정 — 이 스킬은 "
                                "BOARD_DEFAULT_BOARD_ID 대체 경로를 쓰지 않는다 (G3)"))
    forbid_key(findings, where, args, "tagIds",
               "board_create_post 는 `tagNames`(이름 배열)를 받는다")
    tags = args.get("tagNames")
    if tags is not None and check_list(findings, where, tags, "tagNames", 0, 10, False):
        for t in tags:
            if not isinstance(t, str):
                findings.append(Finding("ERROR", where, "C5-TYPE",
                                        "`tagNames` 항목은 문자열이어야 한다"))
            elif not (1 <= len(t) <= 40):
                findings.append(Finding("ERROR", where, "C5-LENGTH",
                                        "태그 `%s` 길이 %d — 허용 1–40자 (§4)"
                                        % (t, len(t))))
    cats = args.get("categoryIds")
    if cats is not None and not isinstance(cats, list):
        findings.append(Finding("ERROR", where, "C5-TYPE",
                                "`categoryIds` 는 id 배열이어야 한다"))


def validate_create_tasks(findings, where, args, bodies):
    if args.get("postId") is None:
        findings.append(Finding("ERROR", where, "C5-REQUIRED", "필수 필드 `postId` 누락"))
    items = args.get("items")
    if not check_list(findings, where, items, "items", 1, 50):
        return
    for i, it in enumerate(items, 1):
        w = "%s · items[%d]" % (where, i)
        if not isinstance(it, dict):
            findings.append(Finding("ERROR", w, "C5-TYPE", "items 항목은 객체여야 한다"))
            continue
        check_str(findings, w, it.get("title"), "title", "task_title")
        detail = it.get("detail")
        if detail is not None:
            check_str(findings, w, detail, "detail", "task_detail", required=False)
        bodies.append(("task[%d] detail" % i, detail))


def validate_update_task_status(findings, where, args, bodies):
    for k in ("postId", "taskId"):
        if args.get(k) is None:
            findings.append(Finding("ERROR", where, "C5-REQUIRED", "필수 필드 `%s` 누락" % k))
    if args.get("status") is None:
        findings.append(Finding("ERROR", where, "C5-REQUIRED", "필수 필드 `status` 누락"))
    check_enum(findings, where, args.get("status"), "status",
               TASK_STATUS, POST_STATUS, "post status")


def validate_add_comment(findings, where, args, bodies):
    if args.get("postId") is None:
        findings.append(Finding("ERROR", where, "C5-REQUIRED", "필수 필드 `postId` 누락"))
    check_str(findings, where, args.get("body"), "body", "comment_body")
    bodies.append(("comment body", args.get("body")))
    forbid_key(findings, where, args, "internal",
               "MCP board_add_comment 는 `{postId, body}` 만 노출한다 — "
               "팀 전용 플래그가 없고 모든 댓글은 공개다")


def validate_set_status(findings, where, args, bodies):
    if args.get("postId") is None:
        findings.append(Finding("ERROR", where, "C5-REQUIRED", "필수 필드 `postId` 누락"))
    has_status = "status" in args and args["status"] is not None
    has_column = "columnId" in args and args["columnId"] is not None
    if has_status and has_column:
        findings.append(Finding("ERROR", where, "C5-EXCLUSIVE",
                                "`status` 와 `columnId` 동시 지정 — 서버가 throw 한다 (§3 #12)"))
    if not has_status and not has_column:
        findings.append(Finding("ERROR", where, "C5-EXCLUSIVE",
                                "`status` · `columnId` 둘 다 없음 — 정확히 하나가 필요하다 (§3 #12)"))
    check_enum(findings, where, args.get("status"), "status",
               POST_STATUS, TASK_STATUS, "task status")


def validate_create_suggestion(findings, where, args, bodies):
    if args.get("postId") is None:
        findings.append(Finding("ERROR", where, "C5-REQUIRED", "필수 필드 `postId` 누락"))
    if not args.get("rationale"):
        findings.append(Finding("ERROR", where, "C5-REQUIRED",
                                "필수 필드 `rationale` 누락 (§3 #13)"))
    bodies.append(("rationale", args.get("rationale")))
    forbid_key(findings, where, args, "tagNames",
               "board_create_suggestion 은 `tagIds`(id 배열)를 받는다 — "
               "board_create_post 와 반대다")
    check_enum(findings, where, args.get("priority"), "priority", PRIORITY)
    dups = args.get("duplicates")
    if dups is not None and isinstance(dups, list):
        for i, d in enumerate(dups, 1):
            w = "%s · duplicates[%d]" % (where, i)
            if not isinstance(d, dict):
                findings.append(Finding("ERROR", w, "C5-TYPE", "duplicates 항목은 객체여야 한다"))
                continue
            for k in ("candidateId", "confidence", "reason"):
                if d.get(k) is None:
                    findings.append(Finding("ERROR", w, "C5-REQUIRED", "`%s` 누락" % k))
            check_enum(findings, w, d.get("confidence"), "confidence", PRIORITY)


def validate_create_release_draft(findings, where, args, bodies):
    check_project_id(findings, where, args.get("projectId"))
    version = args.get("version")
    check_str(findings, where, version, "version", "release_version")
    if isinstance(version, str) and not version.strip():
        findings.append(Finding("ERROR", where, "C5-LENGTH",
                                "`version` 이 공백뿐이다 (§4)"))
    if args.get("name") is not None:
        check_str(findings, where, args.get("name"), "name", "release_name", required=False)
    check_str(findings, where, args.get("body"), "body", "release_body")
    bodies.append(("release body", args.get("body")))
    entries = args.get("entries")
    if not check_list(findings, where, entries, "entries", 1, 50):
        return
    for i, e in enumerate(entries, 1):
        w = "%s · entries[%d]" % (where, i)
        if not isinstance(e, dict):
            findings.append(Finding("ERROR", w, "C5-TYPE", "entries 항목은 객체여야 한다"))
            continue
        check_str(findings, w, e.get("title"), "title", "entry_title")
        check_str(findings, w, e.get("body"), "body", "entry_body")
        bodies.append(("entry[%d] body" % i, e.get("body")))
        check_enum(findings, w, e.get("type"), "type", ENTRY_TYPE)
        if e.get("type") is None:
            findings.append(Finding("ERROR", w, "C5-REQUIRED", "`type` 누락"))
        check_list(findings, w, e.get("postIds"), "postIds", 1, 100)


VALIDATORS = {
    "board_create_post": validate_create_post,
    "board_create_tasks": validate_create_tasks,
    "board_update_task_status": validate_update_task_status,
    "board_add_comment": validate_add_comment,
    "board_set_status": validate_set_status,
    "board_create_suggestion": validate_create_suggestion,
    "board_create_release_draft": validate_create_release_draft,
}


# ---------------------------------------------------------------- 스크럽 · 좌표
def scan_secrets(findings, where, label, text):
    if not isinstance(text, str):
        return
    for pattern, name in SECRET_PATTERNS:
        for m in re.finditer(pattern, text):
            snippet = m.group(0)
            if len(snippet) > 24:
                snippet = snippet[:12] + "…" + snippet[-6:]
            findings.append(Finding("ERROR", where, "G7-LEAK",
                                    "%s 에 %s 로 보이는 값: `%s`"
                                    % (label, name, snippet)))


def count_coords(text):
    if not isinstance(text, str) or not text.strip():
        return {}
    hits = {}
    for pattern, name in COORD_PATTERNS:
        n = len(re.findall(pattern, text))
        if n:
            hits[name] = hits.get(name, 0) + n
    return hits


# ---------------------------------------------------------------- 본체
def validate(path):
    findings = []
    text = path.read_text(encoding="utf-8")
    blocks = parse_blocks(text)
    if not blocks:
        findings.append(Finding("ERROR", str(path), "PARSE",
                                "`## 쓰기 <n>: <도구명>` 헤더를 하나도 찾지 못했다 — "
                                "generator-prompt.md (c) 의 4종 세트 형식을 지킨다"))
        return findings, []

    coord_table = []
    for b in blocks:
        where = "쓰기 %s (%s)" % (b["no"], b["tool"])

        for label in FIELD_LABELS:
            if not re.search(r"^\s*[-*]\s*%s\s*[:：]" % re.escape(label), b["body"], re.M):
                findings.append(Finding("ERROR", where, "FORM",
                                        "4종 세트의 `- %s:` 필드가 없다" % label))

        if b["tool"] not in WRITE_TOOLS:
            findings.append(Finding("ERROR", where, "C5-TOOL",
                                    "`%s` 는 쓰기 7종이 아니다. 허용: %s"
                                    % (b["tool"], " · ".join(sorted(WRITE_TOOLS)))))
            continue

        if b["tool"] in NO_READBACK and NO_READBACK_MARK not in b["body"]:
            findings.append(Finding("ERROR", where, "C4-MARK",
                                    "`%s` 초안에 **[반환 id만 · 재조회 수단 없음]** 표기가 "
                                    "없다 — 이 표기가 그대로 미리보기로 간다 (§3-1)"
                                    % b["tool"]))

        args, err = extract_args(b["body"])
        if err:
            findings.append(Finding("ERROR", where, "PARSE", err))
            continue

        bodies = []
        VALIDATORS[b["tool"]](findings, where, args, bodies)

        raw_args = json.dumps(args, ensure_ascii=False)
        scan_secrets(findings, where, "인자 전문", raw_args)

        for label, body_text in bodies:
            if body_text is None:
                continue
            hits = count_coords(body_text)
            total = sum(hits.values())
            coord_table.append((where, label, total, hits))
            if total == 0:
                findings.append(Finding("ERROR", where, "C1-COORD",
                                        "%s 에 검증 좌표가 0건이다 — 파일 경로 / "
                                        "`파일:라인` / 커밋 해시 / 명령+출력 / 에러 원문 "
                                        "중 최소 1개가 필요하다 (rubric C1)" % label))
            elif total == 1:
                findings.append(Finding("WARN", where, "C1-COORD",
                                        "%s 의 검증 좌표가 1건뿐이다 — 3개월 뒤 이 문장으로 "
                                        "무엇을 재현할 수 있는지 다시 본다" % label))

    return findings, coord_table


def render(path, findings, coord_table):
    out = []
    out.append("# validate_drafts 리포트 — %s" % path.name)
    out.append("")
    errors = [f for f in findings if f.level == "ERROR"]
    warns = [f for f in findings if f.level == "WARN"]
    verdict = "PASS" if not errors else "FAIL"
    out.append("판정: **%s** (ERROR %d · WARN %d)" % (verdict, len(errors), len(warns)))
    out.append("")

    if coord_table:
        out.append("## 증거 좌표 카운트 (rubric C1)")
        out.append("")
        out.append("| 쓰기 | 본문 | 좌표 | 내역 |")
        out.append("|---|---|---|---|")
        for where, label, total, hits in coord_table:
            detail = " · ".join("%s %d" % (k, v) for k, v in sorted(hits.items())) or "—"
            out.append("| %s | %s | %d | %s |" % (where, label, total, detail))
        out.append("")

    if errors:
        out.append("## ERROR — 제출 전 전건 수정")
        out.append("")
        for f in errors:
            out.append("- `%s` **%s** — %s" % (f.code, f.where, f.message))
        out.append("")
    if warns:
        out.append("## WARN — 사람이 판단할 항목")
        out.append("")
        for f in warns:
            out.append("- `%s` **%s** — %s" % (f.code, f.where, f.message))
        out.append("")
    if not findings:
        out.append("지적 사항 없음.")
        out.append("")

    out.append("---")
    out.append("이 검증기가 보지 못하는 것 — 사람 또는 Evaluator 가 판단한다:")
    out.append("- 인용된 파일 경로·커밋 해시가 **실재**하는지 (Evaluator 프로브 2)")
    out.append("- 측정되지 않은 주장(\"회귀 없음\"·\"성능 향상\") (프로브 3)")
    out.append("- 기존 post 와의 **중복** 여부 (프로브 4)")
    out.append("- 공개 보드 대상일 때의 **미공개 내부 정보** (G7 판단 영역)")
    out.append("- id 값이 실제 조회 반환에 존재하는지 (categoryIds · tagIds · columnId · boardId)")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(
        description="drafts_v<n>.md 결정론적 검증 (읽기 전용 · board_* 호출 없음)")
    ap.add_argument("path", help="검증할 drafts_v<n>.md 절대 경로")
    ap.add_argument("--json", action="store_true", help="리포트를 JSON 으로 출력")
    args = ap.parse_args()

    path = Path(args.path)
    if not path.is_file():
        print("BLOCKED: %s" % path, file=sys.stderr)
        return 2

    try:
        findings, coord_table = validate(path)
    except Exception as exc:  # noqa: BLE001 — 검증기 자체 실패는 조용히 넘기지 않는다
        print("VALIDATOR_ERROR: %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return 2

    errors = [f for f in findings if f.level == "ERROR"]
    if args.json:
        print(json.dumps({
            "file": str(path),
            "verdict": "PASS" if not errors else "FAIL",
            "findings": [f.as_dict() for f in findings],
            "coords": [{"where": w, "field": l, "total": t, "detail": h}
                       for w, l, t, h in coord_table],
        }, ensure_ascii=False, indent=2))
    else:
        print(render(path, findings, coord_table))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
