#!/usr/bin/env python3
"""定期請求 WORKSHEET 自動生成スクリプト
毎月1日にcronから実行。当月が発生月のクライアントの定期請求エントリを生成する。
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT        = Path(__file__).parent.parent
CLIENTS_DIR = ROOT / "data" / "clients"
JOBS_DIR    = ROOT / "data" / "jobs"
TICKTICK    = Path.home() / "ticktick" / "bin" / "ticktick"
TT_PROJECT  = "69e64fb64892e90a4be4cbaf"
LOG_FILE    = ROOT / "logs" / "recurring.log"


# ===== ユーティリティ =====

def log(msg):
    print(msg)
    LOG_FILE.parent.mkdir(exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

def get_next_seisaku_number():
    max_num = 10000
    for f in JOBS_DIR.glob("*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            n = d.get("制作番号")
            if isinstance(n, int) and n > max_num:
                max_num = n
        except Exception:
            pass
    return max_num + 1

def job_exists(client_name, billing_month_str):
    for f in JOBS_DIR.glob("*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            if d.get("クライアント") == client_name and d.get("請求月") == billing_month_str:
                return True
        except Exception:
            pass
    return False


# ===== 製品名・期間生成 =====

def get_service_period(billing_year, billing_month, cycle):
    """前払い想定: 請求月の翌月からサービス開始"""
    start_m = billing_month + 1
    start_y = billing_year
    if start_m > 12:
        start_m -= 12
        start_y += 1

    months = 12 if cycle == "1年" else 6
    end_m = start_m + months - 1
    end_y = start_y
    while end_m > 12:
        end_m -= 12
        end_y += 1

    return start_y, start_m, end_y, end_m

def build_product_name(client, teiki, billing_year, billing_month):
    template = teiki.get("品目テンプレ", "")
    cycle    = teiki.get("周期", "半年")
    sy, sm, ey, em = get_service_period(billing_year, billing_month, cycle)
    period = f"({sy}.{sm}月分〜{ey}.{em}月分)"
    hp = client.get("ホームページ", "")
    suffix = f" {hp}" if hp else ""
    return f"{template}{period}{suffix}"


# ===== ジョブ作成 =====

def create_job(client, teiki, billing_year, billing_month):
    seisaku_no        = get_next_seisaku_number()
    client_name       = client.get("社名", "")
    billing_month_str = f"{str(billing_year)[2:]}.{str(billing_month).zfill(2)}"
    today             = datetime.now().strftime("%Y-%m-%d")
    amount            = teiki.get("金額", 0)
    template          = teiki.get("品目テンプレ", "")
    biko              = teiki.get("備考", "")

    job = {
        "制作番号": seisaku_no,
        "クライアント": client_name,
        "末端クライアント": "",
        "製品名": build_product_name(client, teiki, billing_year, billing_month),
        "媒体": "web",
        "敬称": client.get("敬称", "御中"),
        "状態": "請求OK",
        "種別": "通常",
        "外注フラグ": False,
        "依頼日": today,
        "見積日": None,
        "入稿予定日": None,
        "納品予定日": None,
        "納品日": None,
        "請求月": billing_month_str,
        "請求締日": "月末",
        "担当": client.get("オフィス担当者", "はやし"),
        "現在の状況": f"定期請求（{teiki.get('周期','半年')}）自動生成 {today}",
        "サイズ": "", "数量": None, "色数": "", "加工": "", "用紙": "",
        "明細": [
            {
                "区分": "管理費",
                "税率": 10,
                "備考": "",
                "内訳_社内": {"仕込み経費": None, "掛率": None, "計算メモ": ""},
                "選択肢": [
                    {
                        "内容": template,
                        "数量": 1,
                        "単価": amount,
                        "金額": amount,
                        "選択": True,
                        "備考": biko
                    }
                ]
            }
        ],
        "外注": [],
        "メモ": [{"日付": today, "内容": f"定期請求（{teiki.get('周期','半年')}）自動生成"}],
        "相見積もり": [],
        "内訳_社内のみ": [],
        "TickTick_task_id": "",
        "作成日": today,
        "更新日": today,
        "請求対象": True
    }

    safe = client_name.replace(" ", "_").replace("　", "_").replace("/", "_").replace("&", "and")
    filepath = JOBS_DIR / f"{seisaku_no}_{safe}_定期請求.json"
    filepath.write_text(json.dumps(job, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log(f"  作成: {filepath.name}")
    return seisaku_no, filepath


# ===== TickTick =====

def create_ticktick_task(seisaku_no, client_name):
    title  = f"【{seisaku_no}】{client_name} 定期請求"
    result = subprocess.run(
        [str(TICKTICK), "add", title, "--project", "💼仕事"],
        capture_output=True, text=True
    )
    task_id = None
    for line in result.stdout.split("\n"):
        if "id=" in line:
            task_id = line.split("id=")[-1].strip()
            break
    if not task_id:
        log(f"  [警告] TickTick タスク作成失敗")
        return None

    log(f"  TickTick タスク: {task_id}")
    for item in ["見積もり提出", "発注確定", "請求OK", "請求書発行"]:
        subprocess.run([str(TICKTICK), "items-add", task_id, item, "--project", TT_PROJECT],
                       capture_output=True)
    for item in ["見積もり提出", "発注確定", "請求OK"]:
        subprocess.run([str(TICKTICK), "items-check", task_id, item, "--project", TT_PROJECT],
                       capture_output=True)
    log("  TickTick items 設定完了（請求OKまでチェック済み）")
    return task_id


# ===== data.js 再ビルド =====

def rebuild():
    r = subprocess.run(["python3", str(ROOT / "scripts" / "build_data_js.py")],
                       capture_output=True, text=True, cwd=str(ROOT))
    log(f"  {r.stdout.strip()}")


# ===== メイン =====

def main():
    now = datetime.now()
    log(f"\n{'='*50}")
    log(f"=== 定期請求 自動生成 {now.strftime('%Y-%m-%d %H:%M')} ===")

    current_year  = now.year
    current_month = now.month
    billing_month_str = f"{str(current_year)[2:]}.{str(current_month).zfill(2)}"
    log(f"対象月: {billing_month_str}")

    generated = 0

    for client_file in sorted(CLIENTS_DIR.glob("*.json")):
        try:
            client = json.loads(client_file.read_text(encoding="utf-8"))
        except Exception:
            continue

        teiki_list  = client.get("定期請求", [])
        client_name = client.get("社名", "")
        if not teiki_list:
            continue

        for teiki in teiki_list:
            if current_month not in teiki.get("発生月", []):
                continue

            if job_exists(client_name, billing_month_str):
                log(f"[スキップ] {client_name} {billing_month_str} は既に存在")
                continue

            log(f"\n[生成] {client_name} — {teiki.get('品目テンプレ','')}")
            seisaku_no, filepath = create_job(client, teiki, current_year, current_month)
            task_id = create_ticktick_task(seisaku_no, client_name)
            if task_id:
                d = json.loads(filepath.read_text(encoding="utf-8"))
                d["TickTick_task_id"] = task_id
                filepath.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            generated += 1

    if generated > 0:
        log(f"\ndata.js 再ビルド中...")
        rebuild()
        log(f"完了: {generated}件生成")
    else:
        log("今月は対象クライアントなし")

if __name__ == "__main__":
    main()
