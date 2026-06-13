"""
HRS Daily Brief - 自動爬蟲
每天抓取 SAP SuccessFactors 和 Workday 最新功能更新，寫入 data/updates.json
執行方式：python scripts/scrape.py
需要環境變數：FIRECRAWL_API_KEY
"""

import json
import os
import re
import hashlib
import sys
from datetime import datetime, date, timedelta
from pathlib import Path
import urllib.request
import urllib.parse
import urllib.error

# ── 設定 ──────────────────────────────────────────────
FIRECRAWL_API_KEY = os.environ.get("FIRECRAWL_API_KEY", "")
DATA_FILE = Path(__file__).parent.parent / "data" / "updates.json"
TODAY = date.today().isoformat()
LOOKBACK_DAYS = 60  # 搜尋幾天內的新聞

# 模組關鍵字對應表
MODULE_KEYWORDS = {
    "Recruiting": [
        "recruit", "hiring", "talent acquisition", "job requisition",
        "candidate", "applicant", "rcm", "offer letter", "job posting",
    ],
    "Onboarding": [
        "onboard", "new hire", "preboarding", "onb", "day one", "day-one",
    ],
    "Performance & Goals": [
        "performance", "goal", "360", "calibration", "continuous performance",
        "cpd", "feedback", "pm module", "performance form", "rating",
    ],
    "Learning & Development": [
        "learning", "lms", "training", "course", "curriculum",
        "xapi", "tin can", "learning management", "development plan",
    ],
    "Compensation": [
        "compensation", "salary", "bonus", "merit", "pay", "reward",
        "pay equity", "comp planning", "total rewards",
    ],
    "Succession & Development": [
        "succession", "talent pool", "development plan", "mentoring",
        "career path", "skills cloud", "skills ontology", "readiness",
    ],
    "Employee Central": [
        "employee central", "core hr", "position management",
        "absence", "time off", "workforce", "headcount", "org chart",
        "ec payroll", "global benefits",
    ],
    "Payroll": [
        "payroll", "gross-to-net", "pay run", "payslip",
        "tax", "statutory", "payroll connect",
    ],
    "Analytics & Reporting": [
        "analytics", "reporting", "dashboard", "people analytics",
        "workforce analytics", "story report", "canvas report",
        "predictive", "attrition model",
    ],
    "Platform & Integration": [
        "platform", "integration", "api", "admin center", "provisioning",
        "mdf", "odata", "rest api", "intelligent services", "webhook",
        "sap btp", "extension", "migration", "upgrade",
    ],
    "AI & Joule": [
        "joule", "ai agent", "copilot", "generative ai", "large language",
        "llm", "ai-powered", "ai-assisted", "machine learning",
        "workday ai", "intelligent", "natural language",
    ],
}

# 爬取的搜尋查詢列表
SEARCH_QUERIES = [
    # SAP SuccessFactors
    "SAP SuccessFactors new features release 2026 HCM recruiting performance",
    "SAP SuccessFactors 1H 2026 release notes what's new",
    "SAP SuccessFactors Joule AI new capabilities 2026",
    "SAP SuccessFactors employee central compensation learning updates 2026",
    # Workday
    "Workday 2026R1 release new features HCM",
    "Workday 2026 HCM recruiting performance compensation new features",
    "Workday AI agents new capabilities 2026",
    "Workday people analytics learning payroll updates 2026",
]


# ── HTTP helpers ───────────────────────────────────────
def firecrawl_search(query: str, limit: int = 8) -> list[dict]:
    """Call Firecrawl search API and return result list."""
    if not FIRECRAWL_API_KEY:
        print(f"  [SKIP] No FIRECRAWL_API_KEY — skipping: {query[:50]}")
        return []

    payload = json.dumps({
        "query": query,
        "limit": limit,
        "tbs": f"qdr:d{LOOKBACK_DAYS}",
        "scrapeOptions": {
            "formats": ["markdown"],
            "onlyMainContent": True,
        },
    }).encode()

    req = urllib.request.Request(
        "https://api.firecrawl.dev/v1/search",
        data=payload,
        headers={
            "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            return data.get("data", {}).get("web", [])
    except Exception as e:
        print(f"  [ERROR] Firecrawl search failed: {e}")
        return []


# ── 分類邏輯 ───────────────────────────────────────────
def classify_modules(title: str, description: str) -> list[str]:
    """從標題和描述推斷所屬 HRS 模組。"""
    text = (title + " " + description).lower()
    found = []
    for module, keywords in MODULE_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            found.append(module)
    return found if found else ["Platform & Integration"]


def detect_platform(title: str, url: str, description: str) -> str | None:
    """判斷是 SAP SuccessFactors 還是 Workday。"""
    text = (title + " " + url + " " + description).lower()
    if any(k in text for k in ["successfactors", "sap sf", "sap hcm", "joule", "help.sap.com"]):
        return "SAP SuccessFactors"
    if any(k in text for k in ["workday", "workday.com", "2026r1", "2025r2", "wday"]):
        return "Workday"
    return None


def detect_type(title: str, description: str) -> str:
    text = (title + " " + description).lower()
    if any(k in text for k in ["deprecat", "removed", "end of life", "retired"]):
        return "Deprecated"
    if any(k in text for k in ["new feature", "introduces", "launch", "add ", "added ", "now support"]):
        return "New"
    return "Changed"


def make_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:12]


def extract_date(result: dict) -> str:
    """嘗試從結果中取得發布日期，失敗則用今天。"""
    # 嘗試從 markdown 內容中找日期
    text = result.get("markdown", "") or result.get("description", "")
    patterns = [
        r"\b(20\d{2})[/-](\d{1,2})[/-](\d{1,2})\b",
        r"\b(\w+ \d{1,2},?\s+20\d{2})\b",
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            try:
                raw = m.group(0)
                for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%B %d, %Y", "%B %d %Y"):
                    try:
                        return datetime.strptime(raw, fmt).date().isoformat()
                    except ValueError:
                        continue
            except Exception:
                pass
    return TODAY


# ── 主流程 ─────────────────────────────────────────────
def load_existing() -> dict:
    if DATA_FILE.exists():
        with open(DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"lastUpdated": TODAY, "updates": []}


def save(data: dict):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 儲存完成：{len(data['updates'])} 則更新 → {DATA_FILE}")


def scrape_all() -> list[dict]:
    new_items = []
    seen_urls: set[str] = set()

    for query in SEARCH_QUERIES:
        print(f"\n🔍 搜尋：{query[:60]}")
        results = firecrawl_search(query, limit=8)
        print(f"   找到 {len(results)} 筆結果")

        for r in results:
            url = r.get("url", "")
            title = r.get("title", "").strip()
            description = r.get("description", "").strip()

            if not title or not url or url in seen_urls:
                continue
            seen_urls.add(url)

            platform = detect_platform(title, url, description)
            if not platform:
                continue  # 不是 SF 也不是 Workday，跳過

            modules = classify_modules(title, description)
            update_type = detect_type(title, description)
            pub_date = extract_date(r)

            new_items.append({
                "id": make_id(url),
                "platform": platform,
                "title": title,
                "modules": modules,
                "date": pub_date,
                "summary": description or title,
                "type": update_type,
                "availability": "General Availability",
                "configRequired": False,
                "url": url,
                "release": "auto-scraped",
            })

    return new_items


def merge(existing: dict, scraped: list[dict]) -> dict:
    """合併新舊資料，避免重複（以 id 去重）。"""
    existing_ids = {u["id"] for u in existing.get("updates", [])}
    added = 0
    for item in scraped:
        if item["id"] not in existing_ids:
            existing["updates"].append(item)
            existing_ids.add(item["id"])
            added += 1

    # 按日期排序，最新在前
    existing["updates"].sort(key=lambda x: x.get("date", ""), reverse=True)

    # 只保留最近 180 天
    cutoff = (date.today() - timedelta(days=180)).isoformat()
    before = len(existing["updates"])
    existing["updates"] = [u for u in existing["updates"] if u.get("date", TODAY) >= cutoff]
    pruned = before - len(existing["updates"])

    existing["lastUpdated"] = TODAY
    print(f"\n📊 新增 {added} 則 | 移除過期 {pruned} 則 | 總計 {len(existing['updates'])} 則")
    return existing


def main():
    print(f"🚀 HRS Daily Brief 爬蟲啟動 — {TODAY}")
    print(f"   API Key: {'✓ 已設定' if FIRECRAWL_API_KEY else '✗ 未設定（將跳過搜尋）'}")

    existing = load_existing()
    scraped = scrape_all()
    merged = merge(existing, scraped)
    save(merged)


if __name__ == "__main__":
    main()
