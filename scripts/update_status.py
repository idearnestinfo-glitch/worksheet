#!/usr/bin/env python3
"""案件の状態（納品済チェック）更新

使い方:
  python3 scripts/update_status.py 10834 受注
  python3 scripts/update_status.py 10836 経理提出済
  python3 scripts/update_status.py 10837 中止

引数:
  制作番号  (必須)
  新しい状態 (必須)  見積 / 中止 / 受注 / 経理提出済

オプション:
  --bill-month MM 請求月設定 (例: 26.04)
  --delivery-date YYYY-MM-DD 納品日設定
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JOBS_DIR = ROOT / "data" / "jobs"


def main():
    p = argparse.ArgumentParser(description="案件状態の更新")
    p.add_argument("制作番号", help="制作番号 (例: 10834)")
    p.add_argument("状態", choices=["見積", "中止", "受注", "経理提出済"])
    p.add_argument("--bill-month", default=None, help="請求月 (例: 26.04)")
    p.add_argument("--delivery-date", default=None, help="納品日 (例: 2026-04-26)")
    args = p.parse_args()

    target_id = args.制作番号
    new_state = args.状態

    found = None
    for jf in sorted(JOBS_DIR.glob("*.json")):
        data = json.loads(jf.read_text(encoding="utf-8"))
        if str(data.get("制作番号")) == str(target_id):
            found = (jf, data)
            break

    if not found:
        print(f"❌ 制作番号 {target_id} の案件が見つかりません")
        sys.exit(1)

    jf, data = found
    old_state = data.get("状態")
    data["状態"] = new_state
    if args.bill_month is not None:
        data["請求月"] = args.bill_month
    if args.delivery_date is not None:
        data["納品日"] = args.delivery_date
    data["更新日"] = datetime.now().strftime("%Y-%m-%d")
    jf.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"✅ {data.get('クライアント')} / {data.get('製品名')}")
    print(f"   制作番号: {data.get('制作番号')}")
    print(f"   状態: {old_state} → {new_state}")
    if args.bill_month:
        print(f"   請求月: {args.bill_month}")
    if args.delivery_date:
        print(f"   納品日: {args.delivery_date}")

    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_data_js.py")], check=True, cwd=ROOT)


if __name__ == "__main__":
    main()
