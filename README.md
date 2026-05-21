# WORKSHEET — 案件管理システム

デザイン事務所・小規模制作会社向けの案件管理・請求書発行システムです。  
TickTick と連携して工程管理も行います。

---

## 必要なもの

| 必要なもの | 確認方法 |
|---|---|
| Mac（macOS 12以降推奨） | — |
| Python 3（標準搭載） | ターミナルで `python3 --version` |
| Git（標準搭載） | ターミナルで `git --version` |
| TickTick アカウント | https://ticktick.com |
| Claude（Anthropic） | https://claude.ai |

---

## セットアップ手順

### 1. リポジトリをダウンロード

ターミナルを開いて実行：

```bash
git clone https://github.com/【リポジトリURL】 ~/WORKSHEET
```

### 2. 会社情報を設定

`settings.json` をテキストエディタで開き、`【】` で囲まれた箇所をすべて自社情報に書き換えます。

```bash
open ~/WORKSHEET/settings.json
```

### 3. TickTick のプロジェクトIDを調べる

TickTick CLI をセットアップ後（後述）、以下のコマンドで確認：

```bash
~/ticktick/bin/ticktick projects
```

表示されたプロジェクト一覧から仕事用プロジェクトの ID をコピーし、`settings.json` の `ticktick.project_id` に貼り付けます。

### 4. ロゴ・角印を差し替え

`ui/assets/` フォルダ内のファイルを自社のものに差し替えます。

| ファイル名 | 用途 |
|---|---|
| `logo.svg` | 請求書・見積書のヘッダーロゴ |
| `stamp.svg` | 請求書の角印 |

SVG形式を推奨。PNG でも動作します。

### 5. サーバーを起動

```bash
cd ~/WORKSHEET && python3 scripts/serve.py
```

### 6. ブラウザで開く

```
http://localhost:8765/ui/index.html
```

---

## TickTick CLI セットアップ

TickTick との連携には専用の CLI ツールが必要です。  
詳細は担当者（導入支援者）にお問い合わせください。

---

## 毎日の使い方

1. ターミナルで `cd ~/WORKSHEET && python3 scripts/serve.py` を実行
2. ブラウザで `http://localhost:8765/ui/index.html` を開く
3. 案件カードを操作して状態・工程を更新

---

## GitHub への自動バックアップ（推奨）

毎日自動でGitHubにバックアップする設定は導入支援者にご相談ください。

---

## フォルダ構成

```
WORKSHEET/
├── data/
│   ├── jobs/        # 案件JSONファイル（1案件=1ファイル）
│   ├── clients/     # クライアントマスタ
│   ├── vendors/     # 外注先マスタ
│   └── minutes/     # 議事録・進行記録
├── scripts/
│   ├── serve.py         # ローカルサーバー
│   └── build_data_js.py # データ再ビルド
├── ui/
│   ├── index.html   # メイン画面（WORKSHEET）
│   ├── invoice.html # 請求書
│   └── estimate.html # 見積書
└── settings.json    # 会社情報設定
```
