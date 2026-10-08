import json
import re
from datetime import datetime
from playwright.sync_api import sync_playwright

TARGET_STORES = [
    # --- 台北市 (12間) ---
    {"region": "台北市", "name": "台北忠孝遠東SOGO", "url": "https://www.facebook.com/funboxsogo"},
    {"region": "台北市", "name": "三越南西", "url": "https://www.facebook.com/share/1BuSqwADRT/"},
    {"region": "台北市", "name": "三越站前", "url": "https://www.facebook.com/profile.php?id=61593176934292"},
    {"region": "台北市", "name": "天母SOGO", "url": "https://www.facebook.com/profile.php?id=61592597564673"},
    {"region": "台北市", "name": "高島屋百貨", "url": "https://www.facebook.com/ybg5152n/?locale=zh_TW"},
    {"region": "台北市", "name": "信義新天地A8館", "url": "https://www.facebook.com/profile.php?id=61593106704912&locale=zh_TW"},
    {"region": "台北市", "name": "美麗華", "url": "https://www.facebook.com/profile.php?id=61592730395195"},
    {"region": "台北市", "name": "潤泰南港車站店", "url": "https://www.facebook.com/profile.php?id=61592736394851"},
    {"region": "台北市", "name": "天母三越", "url": "https://www.facebook.com/share/1K6XRBMujq/"},
    {"region": "台北市", "name": "遠百信義A13", "url": "https://www.facebook.com/profile.php?id=61551944767554"},
    {"region": "台北市", "name": "南港LaLaport", "url": "http://www.facebook.com/share/14jPaVWXoLJ/?mibextid=wwXlfr"},
    {"region": "台北市", "name": "遠東大巨蛋", "url": "https://reurl.cc/MW3NdL"},

    # --- 新北市 (9間) ---
    {"region": "新北市", "name": "比漾廣場", "url": "https://www.facebook.com/profile.php?id=61592677934745"},
    {"region": "新北市", "name": "板橋遠東", "url": "https://www.facebook.com/share/1BmnHxAaZ7/?mibextid=wwXIfr"},
    {"region": "新北市", "name": "中和環球", "url": "https://www.facebook.com/profile.php?id=61575325211390&locale=zh_TW"},
    {"region": "新北市", "name": "板橋大遠百", "url": "https://www.facebook.com/profile.php?id=61584956488867"},
    {"region": "新北市", "name": "汐科遠雄", "url": "https://www.facebook.com/profile.php?id=61592991209842"},
    {"region": "新北市", "name": "樹林秀泰", "url": "https://www.facebook.com/profile.php?id=61591486063647"},
    {"region": "新北市", "name": "淡水禮萊廣場", "url": "https://www.facebook.com/share/1Db8rVD6Hk/?mibextid=wwXIfr"},
    {"region": "新北市", "name": "宏匯廣場", "url": "https://www.facebook.com/funbox.honhui/?locale=zh_TW"},
    {"region": "新北市", "name": "新店裕隆城", "url": "https://www.facebook.com/share/19E9UZWhK9/?mibextid=wwXIfr"},

    # --- 桃園市 (7間) ---
    {"region": "桃園市", "name": "桃園站前", "url": "https://www.facebook.com/profile.php?id=100064059014450#"},
    {"region": "桃園市", "name": "桃園遠東", "url": "https://www.facebook.com/profile.php?id=100064240476385"},
    {"region": "桃園市", "name": "中壢SOGO", "url": "https://www.facebook.com/profile.php?id=61558958859748"},
    {"region": "桃園市", "name": "中壢大江", "url": "https://www.facebook.com/profile.php?id=100063657227053"},
    {"region": "桃園市", "name": "桃園環球A8", "url": "https://www.facebook.com/profile.php?id=61591728303067"},
    {"region": "桃園市", "name": "台茂購物中心", "url": "https://www.facebook.com/profile.php?id=61590975990981&locale=zh_TW"},
    {"region": "桃園市", "name": "桃園環球A19", "url": "https://www.facebook.com/profile.php?id=100083960592067"}
]

MODEL_REGEX = re.compile(r'([A-Za-z]{2,3}-\d+)', re.IGNORECASE)
LINE_REGEX = re.compile(r'https?:\/\/(?:liff\.line\.me\/[\w\-]+|line\.me\/R\/[\w\-\?=&]+|coupon\.line\.me\/[\w\-]+)')
EXCLUDE_TERMS = ["寶可夢", "PTCG", "鋼彈", "GUNPLA", "TOMICA", "多美", "一番賞", "吉伊卡哇"]
BEYBLADE_TERMS = ["戰鬥陀螺", "BEYBLADE", "極限突破", "BX-", "UX-", "CX-"]

def parse_content(text):
    items = []
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    curr_model = None
    curr_name = None

    for line in lines:
        if any(term in line for term in EXCLUDE_TERMS):
            continue

        m_match = MODEL_REGEX.search(line)
        urls = LINE_REGEX.findall(line)

        if m_match:
            curr_model = m_match.group(1).upper()
            cleaned = LINE_REGEX.sub('', line).strip(" :：-–—*【】👉▶")
            curr_name = cleaned if cleaned else curr_model

        if urls:
            btn_code = curr_model if curr_model else "限定商品"
            btn_title = curr_name if curr_name else btn_code
            items.append({
                "model_code": btn_code,
                "display_name": btn_title,
                "url": urls[0]
            })
            curr_model = None
            curr_name = None
    return items

def scrape_with_browser(page, store):
    items = []
    try:
        # 訪問門市頁面並等待內容渲染
        page.goto(store["url"], timeout=20000, wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
        # 稍微滾動一下觸發貼文載入
        page.mouse.wheel(0, 1500)
        page.wait_for_timeout(1500)
        
        body_text = page.inner_text("body")
        if any(term.lower() in body_text.lower() for term in BEYBLADE_TERMS):
            items = parse_content(body_text)
    except Exception as e:
        print(f"[{store['name']}] 載入超時或受限: {e}")
    return items

def main():
    dashboard = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stores": []
    }

    with sync_playwright() as p:
        iphone = p.devices['iPhone 13']
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(**iphone)
        page = context.new_page()

        for store in TARGET_STORES:
            print(f"正在檢查：{store['name']}...")
            lottery_items = scrape_with_browser(page, store)
            dashboard["stores"].append({
                "name": store["name"],
                "region": store["region"],
                "fb_url": store["url"],
                "items": lottery_items
            })
        browser.close()

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(dashboard, f, ensure_ascii=False, indent=2)
    print("data.json 更新完成！")

if __name__ == "__main__":
    main()
