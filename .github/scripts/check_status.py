"""업로드 정지 감시 — GitHub Actions에서 돈다.

맥에서 돌면 맥이 꺼졌을 때 같이 꺼진다 (2026-09-23 ~ 09-30, 7일간 업로드 0건을
아무도 몰랐다). 그래서 링크인바이오 저장소(GitHub Pages)에 이 파일을 복사해 두고
Actions 스케줄로 돌린다. 실패하면 GitHub가 실패 알림 메일을 보낸다.

맥은 업로드 창마다 status.json을 올린다:
  deployed_at     — 스케줄러가 마지막으로 링크 페이지를 배포한 시각 (업로드 성공과 무관)
  last_upload_at  — 마지막으로 게시에 성공한 시각

둘을 나눠 보면 원인이 갈린다:
  배포가 오래됨           → 맥이 꺼졌거나 스케줄러가 멈춤
  배포는 최근, 업로드는 오래됨 → 스케줄러는 돌지만 업로드 실패 (토큰·헤드라인·대기열)

표준 라이브러리만 쓴다. Actions 러너에는 프로젝트 코드가 없다.
사용: python3 check_status.py status.json
"""
import json
import sys
from datetime import datetime, timedelta, timezone

# 업로드 창 간격은 최대 약 18시간 (18:50 → 다음 날 11:30, ±30분 jitter).
# 창 하나를 놓치는 건 알리지 않고, 두 번 연속 놓치면 알린다.
STALE_HOURS = 36
KST = timezone(timedelta(hours=9))


def _parse(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _ago(now, then):
    return f"{(now - then).total_seconds() / 3600:.0f}시간 전 ({then.astimezone(KST):%m/%d %H:%M} KST)"


def evaluate(status: dict, now: datetime) -> tuple[bool, str]:
    deployed = _parse(status.get("deployed_at"))
    uploaded = _parse(status.get("last_upload_at"))
    limit = timedelta(hours=STALE_HOURS)

    if deployed is None or now - deployed > limit:
        when = _ago(now, deployed) if deployed else "기록 없음"
        return False, (f"NICHEJACK 스케줄러 응답 없음 — 마지막 배포 {when}. "
                       "맥이 꺼졌거나 잠자기 중이거나 스케줄러(launchd)가 멈췄습니다.")
    if uploaded is None or now - uploaded > limit:
        when = _ago(now, uploaded) if uploaded else "기록 없음"
        return False, (f"NICHEJACK 업로드 멈춤 — 마지막 게시 {when}. 스케줄러는 돌고 있습니다. "
                       "IG 토큰 만료, 헤드라인 소진(headlines --pending), 대기열 비었음 중 하나입니다.")
    return True, f"정상 — 마지막 게시 {_ago(now, uploaded)}, 마지막 배포 {_ago(now, deployed)}"


def main(path: str = "status.json") -> int:
    try:
        with open(path, encoding="utf-8") as f:
            status = json.load(f)
    except (OSError, ValueError) as e:
        status = {}
        print(f"status.json을 읽지 못했습니다: {e}")
    ok, msg = evaluate(status, datetime.now(timezone.utc))
    print(msg)
    if not ok:
        print(f"::error::{msg}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "status.json"))
