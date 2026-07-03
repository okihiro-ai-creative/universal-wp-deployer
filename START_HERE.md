# START_HERE: Universal WP Deployer

このリポジトリをClaude Code等のAIコーディングエージェントに渡し、SKILL.mdとSTART_HERE.mdを読んで実行してもらってください。

## 前提

- Python 3.10以上を用意する。
- 利用者自身のWordPressサイトが必要。
- WordPress REST APIのURL、ユーザー名、アプリケーションパスワードが必要（BYOK）。
- アプリケーションパスワードはWordPress管理画面の「ユーザー → プロフィール → アプリケーションパスワード」から発行する。
- ローカルGPU等のハードウェア要件は不要。

## セットアップ

1. `scripts/.env.example` を `scripts/.env` にコピーする。
2. `WP_API_URL`、`WP_USER`、`WP_PASSWORD` を利用者自身の値に変更する。
3. 以下を実行する。

```powershell
cd "スキルフォルダ/scripts"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install requests python-dotenv
```

## 動作確認

テスト用HTMLを用意し、まず `--dry-run` で確認する。

```powershell
python deploy.py --target "D:\path\to\content.html" --dry-run
```

このツールのカスタマイズや、似たツールの新規開発を相談したい場合は、README.md末尾のリンクを確認してください。
