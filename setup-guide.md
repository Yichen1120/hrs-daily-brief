# HRS Daily Brief — 部署指南

## 架構說明

```
500_HRS_Dashboard/
├── index.html              ← 前端網頁（直接在瀏覽器開啟）
├── data/
│   └── updates.json        ← 自動更新的資料檔
├── scripts/
│   └── scrape.py           ← 每日爬蟲（Python 3.11+）
└── .github/
    └── workflows/
        └── daily-scrape.yml ← GitHub Actions 自動排程
```

---

## Step 1：建立 GitHub Repo

1. 到 GitHub 建立新的 **public** repo，例如 `hrs-daily-brief`
2. 把 `500_HRS_Dashboard/` 的所有內容推上去（注意：`.github/` 要放在 repo 根目錄）

```bash
cd 500_HRS_Dashboard
git init
git add .
git commit -m "init: HRS Daily Brief"
git remote add origin https://github.com/YOUR_USERNAME/hrs-daily-brief.git
git push -u origin main
```

---

## Step 2：設定 GitHub Pages

1. Repo → Settings → Pages
2. Source：`Deploy from a branch`
3. Branch：`main` / `(root)`
4. Save → 幾分鐘後網址會出現（格式：`https://YOUR_USERNAME.github.io/hrs-daily-brief/`）

---

## Step 3：加入 Firecrawl API Key

1. 登入 [firecrawl.dev](https://www.firecrawl.dev) 取得 API Key
2. Repo → Settings → Secrets and variables → Actions → New repository secret
3. Name: `FIRECRAWL_API_KEY`，Value: 貼上你的 API Key

---

## Step 4：手動測試爬蟲

在 Actions 頁面 → `Daily HRS Update Scraper` → `Run workflow`

或在本機執行：
```bash
cd 500_HRS_Dashboard
set FIRECRAWL_API_KEY=your_key_here
python scripts/scrape.py
```

---

## 自動更新時間

GitHub Actions 每天 **台灣時間 07:00** 自動執行一次爬蟲，更新 `data/updates.json`，網頁會在下次開啟時自動讀取最新資料。

---

## 手動新增更新

直接編輯 `data/updates.json`，照以下格式新增：

```json
{
  "id": "自定義唯一ID",
  "platform": "SAP SuccessFactors",
  "title": "功能標題",
  "modules": ["Recruiting", "AI & Joule"],
  "date": "2026-06-13",
  "summary": "功能描述，2-3 句話。",
  "type": "New",
  "availability": "General Availability",
  "configRequired": true,
  "url": "https://...",
  "release": "1H 2026"
}
```

**modules 可選值：**
- `Recruiting`
- `Onboarding`
- `Performance & Goals`
- `Learning & Development`
- `Compensation`
- `Succession & Development`
- `Employee Central`
- `Payroll`
- `Analytics & Reporting`
- `Platform & Integration`
- `AI & Joule`
