"""
Universal WP Deployer - WordPress 汎用デプロイスクリプト
======================================================
HTMLファイルを WordPress REST API でデプロイする汎用スクリプト。
"""
import os
import argparse
import requests
import re
import json
import sys
import xmlrpc.client
from urllib.parse import urlparse, urlunparse
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')

# --- 設定読み込み ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(SCRIPT_DIR, ".env")
load_dotenv(ENV_PATH)

DEFAULT_API_URL = os.getenv("WP_API_URL", "")
DEFAULT_USER = os.getenv("WP_USER", "")
DEFAULT_PASSWORD = os.getenv("WP_PASSWORD", "")

# parentは除外しない（0=トップレベルを明示送信するため）
FORBIDDEN_PARAMS = {"template"}

def read_file_with_fallback(file_path: str) -> str:
    """
    ファイルを読み込む。
    BOM付きUTF-8の場合、utf-8-sig でBOMを除去する。
    BOMが残留してしまうとWordPressがブロックを認識しない原因になるため、念入りに除去する。
    """
    # 優先順位: utf-8-sig (BOM自動除去) -> utf-8 -> cp932
    encodings = ["utf-8-sig", "utf-8", "cp932"]

    for encoding in encodings:
        try:
            with open(file_path, "r", encoding=encoding) as f:
                content = f.read()

                # utf-8等で読んだ場合にBOM(\ufeff)が残っていたら除去する
                if content.startswith("\ufeff"):
                    print(f"[WARN] BOM detected and removed (read as {encoding})")
                    content = content.lstrip("\ufeff")

                print(f"[INFO] Successfully read file using: {encoding}")
                return content
        except (UnicodeDecodeError, UnicodeError):
            continue

    raise ValueError(f"ファイルを読み込めません: {file_path}")


def extract_metadata(content: str) -> dict:
    """ファイル先頭のコメントブロックからメタデータを抽出する"""
    metadata = {}
    comment_match = re.search(r"<!--\s*(.*?)\s*-->", content, re.DOTALL)
    if not comment_match:
        return metadata

    for line in comment_match.group(1).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip().upper()
            value = value.strip()
            if key in [
                "TITLE",
                "ID",
                "SLUG",
                "STATUS",
                "PASSWORD",
                "PARENT",
                "TEMPLATE",
                "SEO_TITLE",
                "SEO_DESCRIPTION",
                "META_DESCRIPTION",
                "SEO_KEYWORDS",
                "EYECATCH_ALT",
            ]:
                metadata[key] = value

    return metadata


def build_xmlrpc_url(api_url: str) -> str:
    """WP REST API URLから同一サイトのxmlrpc.php URLを作る"""
    parsed = urlparse(api_url)
    path = parsed.path.split("/wp-json", 1)[0].rstrip("/") + "/xmlrpc.php"
    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))


def update_wp_seo_meta(api_url: str, username: str, password: str,
                           post_type: str,
                           post_id: int, metadata: dict) -> bool:
    """SEO欄をREST metaで更新する"""
    seo_fields = {
        "the_page_seo_title": metadata.get("SEO_TITLE"),
        "the_page_meta_description": (
            metadata.get("SEO_DESCRIPTION") or metadata.get("META_DESCRIPTION")
        ),
        "the_page_meta_keywords": metadata.get("SEO_KEYWORDS"),
        "acl_eyecatch_alt": metadata.get("EYECATCH_ALT"),
    }
    seo_fields = {k: v for k, v in seo_fields.items() if v}
    if not seo_fields:
        return True

    auth = (username, password)
    headers = {"Content-Type": "application/json"}
    rest_endpoint = f"{api_url}/{post_type}/{post_id}"
    try:
        res = requests.post(rest_endpoint, json={"meta": seo_fields}, auth=auth, headers=headers)
        if res.status_code in [200, 201]:
            print("[SEO] SEOメタをRESTで更新しました。")
            return True
        print(f"[SEO] RESTメタ更新に失敗: {res.status_code} {res.text[:300]}")
    except Exception as exc:
        print(f"[SEO] RESTメタ更新に失敗: {exc}")

    # RESTでmeta更新できない環境向けの予備経路。
    xmlrpc_url = build_xmlrpc_url(api_url)
    server = xmlrpc.client.ServerProxy(xmlrpc_url, allow_none=True)

    try:
        existing = server.wp.getPost(0, username, password, int(post_id), ["custom_fields"])
        current_fields = existing.get("custom_fields", [])
        by_key = {}
        for field in current_fields:
            key = field.get("key")
            if key in seo_fields and key not in by_key:
                by_key[key] = field.get("id")

        custom_fields = []
        for key, value in seo_fields.items():
            field = {"key": key, "value": value}
            if by_key.get(key):
                field["id"] = by_key[key]
            custom_fields.append(field)

        server.wp.editPost(0, username, password, int(post_id), {"custom_fields": custom_fields})
        print("[SEO] SEOメタをXML-RPCで更新しました。")
        return True
    except Exception as exc:
        print(f"❌ SEOメタ更新に失敗: {exc}")
        return False


def wrap_as_wp_block(content: str) -> str:
    """WordPressカスタムHTMLブロックとしてラップする"""
    if "<!-- wp:html -->" in content:
        return content
    cleaned = re.sub(r'<!--\s*/?wp:html\s*-->', '', content, flags=re.IGNORECASE)
    cleaned = cleaned.strip()
    return f"<!-- wp:html -->\n{cleaned}\n<!-- /wp:html -->"


def deploy(target_path: str, api_url: str, username: str, password: str,
           post_type: str = "pages", dry_run: bool = False):
    if not os.path.exists(target_path):
        print(f"❌ ファイルが見つかりません: {target_path}")
        return False

    if not username or not password or not api_url:
        print("❌ 認証情報が不足しています。.env ファイルまたは引数を確認してください。")
        return False

    # --- ファイル読み込み ---
    print(f"Reading file: {target_path}")
    content = read_file_with_fallback(target_path)
    metadata = extract_metadata(content)

    title = metadata.get("TITLE", os.path.basename(target_path))
    post_id = metadata.get("ID")
    slug = metadata.get("SLUG")
    status = metadata.get("STATUS", "publish")
    page_password = metadata.get("PASSWORD")
    seo_title = metadata.get("SEO_TITLE")
    seo_description = metadata.get("SEO_DESCRIPTION") or metadata.get("META_DESCRIPTION")
    seo_keywords = metadata.get("SEO_KEYWORDS")
    eyecatch_alt = metadata.get("EYECATCH_ALT")
    # PARENT: HTMLに PARENT: X と明示した場合のみ送信する。
    # 明示しない場合はフィールド自体を送らず、WP管理画面の設定を維持する。
    parent = metadata.get("PARENT")  # None = 未指定（送信しない）
    parent_int = int(parent) if parent is not None else None
    template = metadata.get("TEMPLATE")

    # メタデータコメントをコンテンツから除去（WPがクラシックブロックとして誤認識するのを防ぐ）
    if metadata:
        content = re.sub(r'^\s*<!--.*?-->\s*', '', content, count=1, flags=re.DOTALL)

    # --- HTMLブロックラップ ---
    if target_path.lower().endswith(".html"):
        final_content = wrap_as_wp_block(content)
    else:
        final_content = content

    # [DEBUG] 文字化けチェック
    print(f"Title (preview): {title[:20]}...")
    print(f"Content Start (preview): {final_content[:50]}...")

    auth = (username, password)
    headers = {"Content-Type": "application/json"}

    print(f"\n{'='*60}")
    print(f"  UNIVERSAL WP DEPLOYER v2.4 (Parent Preserve)")
    print(f"  ファイル: {os.path.basename(target_path)}")
    print(f"  タイトル: {title}")
    print(f"  ID: {post_id or '(新規作成)'}")
    print(f"  スラッグ: {slug or '(自動)'}")
    print(f"  親ページID: {parent_int if parent_int is not None else '(WP設定を維持)'}")
    print(f"  テンプレート: {template or '(未指定)'}")
    print(f"  SEOタイトル: {seo_title or '(未指定)'}")
    print(f"  SEO説明: {seo_description or '(未指定)'}")
    print(f"  SEOキーワード: {seo_keywords or '(未指定)'}")
    print(f"  アイキャッチALT: {eyecatch_alt or '(未指定)'}")
    print(f"  モード: {'DRY-RUN' if dry_run else 'DEPLOY'}")
    print(f"{'='*60}\n")

    if dry_run:
        print("[DRY-RUN] デプロイは実行されません。")
        return True

    # 共通データ構築
    data = {
        "title": title,
        "content": final_content,
        "status": status,
    }
    if parent_int is not None:
        data["parent"] = parent_int  # HTMLに PARENT: X が明示されている場合のみ送信
    if slug:
        data["slug"] = slug
    if page_password:
        data["password"] = page_password
    if template:
        data["template"] = template

    # 送信禁止パラメータ除外
    data = {
        k: v for k, v in data.items()
        if k not in FORBIDDEN_PARAMS
    }

    # APIリクエスト
    if post_id:
        endpoint = f"{api_url}/{post_type}/{post_id}"
        print(f"[UPDATE] ID {post_id} を更新中...")
        res = requests.post(endpoint, json=data, auth=auth, headers=headers)
    else:
        # 新規作成（段階的デプロイ）
        # Step 1
        base_endpoint = f"{api_url}/{post_type}"
        step1_data = {"title": title, "status": "draft", "parent": parent}
        if slug: step1_data["slug"] = slug
        if template: step1_data["template"] = template
        print("[Step 1/3] 最小構成でdraft作成...")
        res = requests.post(base_endpoint, json=step1_data, auth=auth, headers=headers)
        if res.status_code not in [200, 201]:
            print(f"❌ Step 1 失敗: {res.status_code}")
            return False

        new_id = res.json().get("id")
        print(f"   OK (ID: {new_id})")

        # Step 2
        step2_data = {"content": final_content}
        step2_endpoint = f"{api_url}/{post_type}/{new_id}"
        print("[Step 2/3] コンテンツ注入...")
        res = requests.post(step2_endpoint, json=step2_data, auth=auth, headers=headers)
        if res.status_code not in [200, 201]:
            print(f"❌ Step 2 失敗: {res.status_code}")
            return False

        # Step 3
        print("[Step 3/3] ステータス確定...")
        step3_data = {"status": status}
        if page_password: step3_data["password"] = page_password
        res = requests.post(step2_endpoint, json=step3_data, auth=auth, headers=headers)
        if res.status_code not in [200, 201]:
            print(f"❌ Step 3 失敗: {res.status_code}")
            return False

    # 結果確認（更新・新規共通）
    if res.status_code in [200, 201]:
        result = res.json()
        print(f"\n✅ 成功!")
        print(f"   ID: {result.get('id')}")
        print(f"   Link: {result.get('link')}")
        if not update_wp_seo_meta(api_url, username, password, post_type, int(result.get("id")), metadata):
            return False
        return True
    else:
        print(f"❌ 失敗: {res.status_code}")
        try:
            print(f"   Response: {res.json()}")
        except:
            print(f"   Response: {res.text[:500]}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Universal WP Deployer")
    parser.add_argument("--target", required=True, help="デプロイ対象ファイルのパス")
    parser.add_argument("--type", default="pages", help="投稿タイプ (pages, posts, custom_post_type)")
    parser.add_argument("--user", default=DEFAULT_USER, help="WordPressユーザー名")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="アプリケーションパスワード")
    parser.add_argument("--endpoint", default=DEFAULT_API_URL, help="WordPress API URL")
    parser.add_argument("--dry-run", action="store_true", help="実行せずに確認のみ")

    args = parser.parse_args()

    deploy(args.target, args.endpoint, args.user, args.password, args.type, args.dry_run)
