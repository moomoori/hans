# blogger_publisher.py  ―  Blogger 자동 포스팅 및 텔레그램 보고서

import os
import re
import json
import pickle
import time
import requests
from pathlib import Path
from datetime import datetime

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# ════════════════════════════════════════════
#  설정
# ════════════════════════════════════════════
BLOG_ID     = "375095031189803359"      
POSTS_DIR   = Path("posts")               
PUBLISHED   = Path("published.json")

TELEGRAM_TOKEN = '8493649546:AAEdgEc2h6BLObDPWaJzNKkAcNtSAUIdiAc'
CHAT_ID = '6095382920'
# ════════════════════════════════════════════

# 주소 복붙 오류 수정 완료
SCOPES      = ["https://www.googleapis.com/auth/blogger"]
TOKEN_FILE  = Path("token.pickle")
SECRETS     = Path("client_secrets.json")

def send_tg_report(published_posts: list):
    if not published_posts: return
    lines = [
        f"✅ **[블로그 자동 발행 완료]**",
        f"총 {len(published_posts)}개의 글이 등록되었습니다.\n",
        "---"
    ]
    for i, post in enumerate(published_posts, 1):
        lines.append(f"🔹 **{i}. {post['title']}**")
        lines.append(f"🔗 [글 바로가기 확인]({post['url']})\n")
    
    lines.append("---")
    lines.append(f"⏰ 발행 완료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # 주소 복붙 오류 수정 완료
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                      json={"chat_id": CHAT_ID, "text": "\n".join(lines), "parse_mode": "Markdown"}, timeout=5)
        print("\n📱 텔레그램으로 발행 보고서가 전송되었습니다!")
    except Exception as e:
        print(f"\n❌ 텔레그램 전송 실패: {e}")

def get_credentials() -> Credentials:
    creds = None
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, "rb") as f: creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(SECRETS), SCOPES)
            creds = flow.run_local_server(port=0, open_browser=True)
        with open(TOKEN_FILE, "wb") as f: pickle.dump(creds, f)
    return creds

def load_published() -> dict:
    if PUBLISHED.exists(): return json.loads(PUBLISHED.read_text(encoding="utf-8"))
    return {}

def save_published(data: dict):
    PUBLISHED.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def parse_html(filepath: Path) -> dict:
    content = filepath.read_text(encoding="utf-8")
    title = re.search(r"<title>(.*?)</title>", content)
    desc  = re.search(r'<meta name="description" content="(.*?)"', content)
    keywords_meta = re.search(r'<meta name="keywords" content="(.*?)"', content)
    body  = re.search(r"<article>(.*?)</article>", content, re.DOTALL)

    tags = [t.strip() for t in keywords_meta.group(1).split(",") if t.strip()] if keywords_meta else []

    return {
        "title":   title.group(1) if title else filepath.stem,
        "desc":    desc.group(1)  if desc  else "",
        "content": body.group(1)  if body  else content,
        "tags":    tags
    }

def publish_post(service, post_data: dict) -> dict:
    body = {
        "title": post_data["title"],
        "content": post_data["content"],
    }
    if post_data.get("tags"):
        body["labels"] = post_data["tags"]

    result = service.posts().insert(
        blogId=BLOG_ID,
        body=body,
        isDraft=False,
    ).execute()
    return result

def main():
    print("=== Blogger 자동 포스팅 시작 ===\n")
    html_files = sorted(POSTS_DIR.glob("*.html"))
    if not html_files: return
    
    published = load_published()
    pending   = [f for f in html_files if f.stem not in published]

    if not pending:
        print("발행할 새 글이 없습니다.")
        return

    print(f"발행 대기 중인 글: {len(pending)}편\n")
    creds   = get_credentials()
    service = build("blogger", "v3", credentials=creds)

    successfully_published = []

    for i, filepath in enumerate(pending, 1):
        print(f"[{i}/{len(pending)}] '{filepath.stem}' 발행 중...")
        try:
            post_data = parse_html(filepath)
            result    = publish_post(service, post_data)

            published[filepath.stem] = {
                "blogger_post_id": result["id"],
                "url":             result["url"],
                "published_at":    datetime.now().isoformat(),
                "title":           result["title"],
            }
            save_published(published)
            successfully_published.append({"title": result["title"], "url": result["url"]})
            print(f"  발행 완료! URL: {result['url']}\n")
            if i < len(pending): time.sleep(3)
        except Exception as e:
            print(f"  오류 발생: {e}\n"); continue

    print("=== 완료! published.json에서 발행 내역을 확인하세요 ===")
    send_tg_report(successfully_published)

if __name__ == "__main__":
    main()