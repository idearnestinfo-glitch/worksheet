#!/bin/bash
# IDEARNEST → iCloud バックアップ
# 使い方: bash ~/IDEARNEST/scripts/backup_to_icloud.sh
# 推奨: 1日1回実行（cron / launchd / 手動）

set -e

SRC="$HOME/IDEARNEST/"
DST_DIR="$HOME/Library/Mobile Documents/com~apple~CloudDocs/@Works（2019.08〜）/@CarryingDATA/claude/@仕事マネージャー経理管理/IDEARNEST_Backup"

mkdir -p "$DST_DIR"

# rsync: ローカルが正本、出力PDFと.gitは除外
rsync -a --delete \
  --exclude="/pdf/" \
  --exclude="/.git/" \
  --exclude=".DS_Store" \
  "$SRC" "$DST_DIR/"

NOW=$(date "+%Y-%m-%d %H:%M:%S")
echo "$NOW" > "$DST_DIR/.last_backup"

echo "✅ バックアップ完了"
echo "   from: $SRC"
echo "   to  : $DST_DIR"
echo "   時刻: $NOW"
