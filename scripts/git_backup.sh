#!/bin/bash
# IDEARNEST 自動バックアップ
# 変更があればコミット＆プッシュ、なければスキップ

set -e
REPO="/Users/hayashihiroko/IDEARNEST"
LOG="$REPO/logs/git_backup.log"

mkdir -p "$REPO/logs"

cd "$REPO"

# 変更チェック（staging含む）
git add -A
if git diff --cached --quiet; then
  echo "$(date '+%Y-%m-%d %H:%M') [skip] 変更なし" >> "$LOG"
  exit 0
fi

# コミット
git commit -m "auto-backup: $(date '+%Y-%m-%d %H:%M')" >> "$LOG" 2>&1

# プッシュ
git push origin main >> "$LOG" 2>&1
echo "$(date '+%Y-%m-%d %H:%M') [ok] プッシュ完了" >> "$LOG"
