#!/usr/bin/env python3
"""案件一覧をCLI表示

使い方:
  python3 scripts/list_jobs.py                    # 全件
  python3 scripts/list_jobs.py --active           # 進行中のみ（受注+見積）
  python3 scripts/list_jobs.py --status 受注      # 状態指定
  python3 scripts/list_jobs.py --client "オフィス" # クライアント絞り込み
  python3 scripts/list_jobs.py --bill-month 26.04 # 請求月指定
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JOBS_DIR = ROOT / "data" / "jobs"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--active", action="store_true", help="進行中（受注+見積）のみ")
    p.add_argument("--status", default=None)
    p.add_argument("--client", default=None)
    p.add_argument("--bill-month", default=None)
    p.add_argument("--type", dest="job_type", default=None)
    args = p.parse_args()

    jobs = []
    for jf in sorted(JOBS_DIR.glob("*.json")):
        try:
            jobs.append(json.loads(jf.read_text(encoding="utf-8")))
        except Exception as e:
            print(f"⚠️ 読み込み失敗 {jf.name}: {e}")

    # filter
    if args.active:
        jobs = [j for j in jobs if j.get("状態") in ("受注", "見積")]
    if args.status:
        jobs = [j for j in jobs if j.get("状態") == args.status]
    if args.client:
        q = args.client
        jobs = [j for j in jobs if q in (j.get("クライアント") or "") or q in (j.get("末端クライアント") or "")]
    if args.bill_month:
        jobs = [j for j in jobs if j.get("請求月") == args.bill_month]
    if args.job_type:
        jobs = [j for j in jobs if j.get("種別") == args.job_type]

    # sort: 制作番号 desc
    jobs.sort(key=lambda j: -(j.get("制作番号") or 0))

    if not jobs:
        print("(該当案件なし)")
        return

    print(f"{'番号':>6} {'状態':<8} {'種別':<6} {'外注':<3} {'担当':<6} {'クライアント':<30} {'製品名'}")
    print("─" * 110)
    for j in jobs:
        seg = str(j.get("制作番号") or "撮影")
        st = j.get("状態") or "-"
        tp = j.get("種別") or "-"
        ga = "○" if j.get("外注フラグ") else " "
        ta = j.get("担当") or "-"
        cl = (j.get("クライアント") or "")[:28]
        pr = (j.get("製品名") or "")[:50]
        print(f"{seg:>6} {st:<8} {tp:<6} {ga:<3} {ta:<6} {cl:<30} {pr}")


if __name__ == "__main__":
    main()
