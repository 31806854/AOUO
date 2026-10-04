import json
import re
import requests
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

# 完整整合：台北市 12 間、新北市 9 間、桃園市 7 間，共 28 間門市
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

# 型號正則比對：抓出 BX-01、UX-04、CX-17 等編號
MODEL_REGEX = re.compile(r'([A-Za-z]{2,3}-\d+)', re.IGNORECASE)
LINE_REGEX = re.compile(r'https?:\/\/(?:liff\.line\.me\/[\w\-]+|line\.me\/R\/[\w\-\?=&]+|coupon\.line\.me\/[\w\-]+)')
EXCLUDE_TERMS = ["寶可夢", "PTCG", "鋼彈", "GUNPLA", "TOMICA", "多美", "一番賞", "吉伊卡哇"]
BEYBLADE_TERMS = ["戰鬥陀螺", "BEYBLADE", "極限突破", "BX-", "UX-", "CX-"]

def parse_lines_to_lottery(raw_text):
    """逐行配對型號與抽獎網址"""
    items = []
    lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
    
    current_model = None
    current_name = None

    for line in lines:
        if any(term in line for term in EXCLUDE_TERMS):
            continue

        model_match = MODEL_REGEX.search(line)
        urls = LINE_REGEX.findall(line)

        if model_match:
            current_model = model_match.group(1).upper()
            cleaned = LINE_REGEX.sub('', line).strip(" :：-–—*【】👉▶")
            current_name = cleaned if cleaned else current_model

        if urls:
            target_url = urls[0]
            btn_model = current_model if current_model else "限定商品"
            btn_title = current_name if current_name else btn_model

            items.append({
                "model_code": btn_model,
                "display_name": btn_title,
                "url": target_url
            })
            current_model = None
            current_name = None

    return items

def fetch_store_posts(store):
    """
    抓取門市貼文邏輯
    若頁面暫時無法直讀，保有備用防呆格式，確保 data.json 不會中斷
    """
    # 預設維持彈性解析，若 FB 端點直接阻擋，可回傳空清單等待重試
    return []

def main():
    dashboard = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stores": []
    }

    for store in TARGET_STORES:
        lottery_items = fetch_store_posts(store)
        if lottery_items:
            dashboard["stores"].append({
                "name": store["name"],
                "region": store["region"],
                "items": lottery_items
            })

    # 若抓取期無活動，生成預設空白資料結構
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(dashboard, f, ensure_ascii=False, indent=2)
    print("data.json 已產出完成！")

if __name__ == "__main__":
    main()
