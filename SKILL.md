---
name: universal-wp-deployer
description: HTMLファイル1つを渡すだけでWordPress REST APIにデプロイする汎用スキル。固定ページ・通常投稿・カスタム投稿タイプに対応。
---

# Universal WP Deployer

## 概要

WordPress REST API を使用して、HTMLファイルの内容をWordPressサイトにデプロイする汎用ツール。
ファイル先頭のメタデータコメントを読み取り、ID指定で更新・IDなしで新規作成を自動判別する。

**スクリプト場所**: `scripts/deploy.py`

---

## 外部サービス依存

- WordPress REST API を使用する。
- 利用者自身のWordPressサイト、ユーザー名、アプリケーションパスワードが必要（BYOK）。
- WordPress管理画面で「ユーザー → プロフィール → アプリケーションパスワード」から発行し、`scripts/.env` に設定する。

---

## 送信禁止パラメータ（絶対厳守）

| パラメータ | 理由 | 対処 |
|---|---|---|
| `template` | WordPressテーマやCPT側の許可設定に依存し、API経由で無効または事故要因になることがある | WP管理画面で手動設定 |

### 親ページ（parent）に関する重要Tips

REST API経由での `parent` 指定は、テーマ・プラグイン・CPT設定によってURL階層へ反映されないことがある。

- HTMLメタデータに `PARENT:` を明示した場合のみ送信する。
- 子ページ化（URL階層化）したい場合は、WP管理画面の固定ページ一覧から手動で親ページを指定する。

---

## `--type` の指定

`--type` を省略すると `pages`（固定ページ）になる。CPT へデプロイする場合は、利用者自身のWordPressで有効なRESTベース名を指定する。

| --type 値 | 用途 |
|---|---|
| （省略） | 固定ページ |
| posts | 通常投稿 |
| 任意のRESTベース名 | 利用者環境のカスタム投稿タイプ |

新CPT初回デプロイ後に404になる場合は、WP管理画面 → 設定 → パーマリンク → 変更を保存、でパーマリンクを再生成する。

---

## 絶対ルール（事故防止）

### STATUS: publish を維持する

- 既存の公開記事を再デプロイする場合、`STATUS: publish` を必ず確認してからデプロイする。
- `STATUS: draft` のまま再デプロイすると、公開済み記事が非公開に戻る。
- ユーザーが明示的に非公開化を依頼した場合のみ `draft` / `private` を使う。

### 初回デプロイ後は ID を必ず HTML に書き込む

- 新規作成後、WP が返した Post ID を HTML 冒頭コメントの `ID:` 行に追記する。
- 書き忘れると次回デプロイで重複新規作成が起きる。

---

## セットアップ（初回のみ）

```powershell
cd "スキルフォルダ/scripts"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install requests python-dotenv
copy .env.example .env
```

`.env` に利用者自身のWordPress情報を記入する。

---

## 使い方

### 1. デプロイ対象HTMLのメタデータ形式

```html
<!--
TITLE: 記事のタイトル
ID: 12345
SLUG: my-new-post
STATUS: publish
PASSWORD: optional_password
PARENT: 0
SEO_TITLE: SEOタイトル
SEO_DESCRIPTION: メタディスクリプション
SEO_KEYWORDS: キーワード
EYECATCH_ALT: アイキャッチ画像ALT
-->
```

| フィールド | 必須 | 説明 |
|---|---|---|
| TITLE | ○ | ページタイトル |
| ID | △ | 既存ページ更新時は必須。新規作成時は省略。新規作成後に発行されたIDを必ず追記する |
| SLUG | △ | URLスラッグ。省略時は自動生成 |
| STATUS | △ | `publish` / `draft` / `private`（デフォルト: publish） |
| PASSWORD | △ | パスワード保護が必要な場合に指定 |
| PARENT | △ | 親ページID。省略時は送信しない |
| SEO_TITLE | △ | SEOタイトル用メタキーへ送信 |
| SEO_DESCRIPTION | △ | メタディスクリプション用メタキーへ送信 |
| SEO_KEYWORDS | △ | メタキーワード用メタキーへ送信 |
| EYECATCH_ALT | △ | アイキャッチ画像ALT用メタキーへ送信 |

SEOメタの保存には、対象投稿タイプ側でメタキーが `show_in_rest => true` 登録されている必要がある。

### 2. 実行コマンド

```powershell
cd "スキルフォルダ/scripts"
.\.venv\Scripts\Activate.ps1

python deploy.py --target "D:\path\to\content.html"
python deploy.py --target "D:\path\to\content.html" --type posts
python deploy.py --target "D:\path\to\content.html" --type custom_post_type
python deploy.py --target "D:\path\to\content.html" --dry-run
```

---

## ファイル構成

```text
universal-wp-deployer/
├── SKILL.md
└── scripts/
    ├── deploy.py
    ├── .env.example
    └── .venv/          # 利用者が作成
```

---

## メディアアップロード（画像をWPメディアライブラリに登録）

画像ファイルをWPメディアライブラリへアップロードしてALTテキストを設定する場合も、利用者自身のWordPress認証情報を使用する。

- ファイル名はアップロード前に英数字・ハイフン中心へリネームする。
- ALTテキストはページ内容に合わせて設定する。
- アップロード後のURLをHTMLの `<img src>` に埋め込む。
