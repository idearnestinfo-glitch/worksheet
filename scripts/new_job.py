#!/usr/bin/env python3
"""新規案件レコード作成

使い方:
  python3 scripts/new_job.py \
    --client "有限会社オフィス" \
    --product "遠州小巾HP制作" \
    --end-client "遠州小巾" \
    --gaichu \
    --status 受注 \
    --medium web \
    --tanto はやし

  # 撮影案件
  python3 scripts/new_job.py --type 撮影 --client "高野" --product "ポートレート撮影" --tanto はやし
"""
import argparse
import json
import re
import subprocess
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SETTINGS_PATH = ROOT / "settings.json"
JOBS_DIR = ROOT / "data" / "jobs"


def safe_filename(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    return re.sub(r"[\\/:*?\"<>|\s]+", "_", s).strip("_")


def main():
    p = argparse.ArgumentParser(description="新規案件JSON作成")
    p.add_argument("--client", required=True, help="クライアント（FM上の請求先）")
    p.add_argument("--product", required=True, help="製品名")
    p.add_argument("--end-client", default="", help="末端クライアント（外注の場合の最終ユーザー）")
    p.add_argument("--medium", default="", help="媒体 (web / 印刷物 / 撮影 / その他)")
    p.add_argument("--status", default="見積", choices=["見積", "中止", "受注", "経理提出済"])
    p.add_argument("--type", dest="job_type", default="通常", choices=["通常", "撮影"])
    p.add_argument("--gaichu", action="store_true", help="IDEARNESTが下請の案件")
    p.add_argument("--tanto", default="はやし")
    p.add_argument("--ticktick-id", default="", help="既存TickTickタスクIDがあれば")
    p.add_argument("--ticktick-title", default="", help="TickTickタスクタイトル")
    p.add_argument("--keisho", default="御中", help="敬称")
    args = p.parse_args()

    settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))

    # 採番（撮影は番号なし）
    if args.job_type == "撮影":
        seg_id = None
    else:
        seg_id = settings["next_job_number"]

    today = datetime.now().strftime("%Y-%m-%d")

    job = {
        "制作番号": seg_id,
        "クライアント": args.client,
        "末端クライアント": args.end_client or None,
        "製品名": args.product,
        "媒体": args.medium,
        "敬称": args.keisho,
        "状態": args.status,
        "種別": args.job_type,
        "外注フラグ": args.gaichu,
        "依頼日": today,
        "見積日": None,
        "入稿予定日": None,
        "納品予定日": None,
        "納品日": None,
        "請求月": None,
        "請求締日": "月末",
        "担当": args.tanto,
        "サイズ": "",
        "数量": None,
        "色数": "",
        "加工": "",
        "用紙": "",
        "明細": [],
        "外注": [],
        "メモ": [],
        "相見積もり": [],
        "内訳_社内のみ": [],
        "TickTick_task_id": args.ticktick_id,
        "TickTick_title": args.ticktick_title,
        "作成日": today,
        "更新日": today,
    }

    # ファイル名生成
    prefix = str(seg_id) if seg_id else "撮影"
    client_short = safe_filename(args.client)[:20]
    product_short = safe_filename(args.product)[:30]
    fname = f"{prefix}_{client_short}_{product_short}.json"
    out = JOBS_DIR / fname

    if out.exists():
        print(f"❌ 同名ファイルが既に存在: {out.relative_to(ROOT)}")
        sys.exit(1)

    out.write_text(json.dumps(job, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # settings 更新（撮影以外のみ採番カウンタ進める）
    if args.job_type != "撮影":
        settings["next_job_number"] = seg_id + 1
        SETTINGS_PATH.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"✅ 作成: {out.relative_to(ROOT)}")
    print(f"   制作番号: {seg_id or '(撮影)'}")
    print(f"   クライアント: {args.client}")
    if args.end_client:
        print(f"   末端: {args.end_client}")
    print(f"   状態: {args.status}")
    if args.gaichu:
        print(f"   外注フラグ: ON（請求先=元請）")

    # data.js 再生成
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_data_js.py")], check=True, cwd=ROOT)


if __name__ == "__main__":
    main()
