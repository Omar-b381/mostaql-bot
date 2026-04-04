import os
import time
import requests
from bs4 import BeautifulSoup
from google import genai
from dotenv import load_dotenv

# تحميل المتغيرات
load_dotenv()

# ==========================================
# Configuration
# ==========================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY     = os.getenv("GEMINI_API_KEY")

KEYWORDS = [
    "تحليل بيانات", "محلل بيانات", "احصاء", "إحصاء", "إحصائي",
    "Data Analysis", "Data Analyst", "Data Science", "Excel", "إكسيل",
    "Power BI", "Tableau", "Python", "SQL", "Dashboard", "داشبورد"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

SCRAPE_URL    = "https://mostaql.com/projects?keyword=بيانات"
SEEN_FILE     = "last_project.txt"
REQUEST_DELAY = 3

# ==========================================
# Gemini
# ==========================================
client = genai.Client(api_key=GEMINI_API_KEY)

# ==========================================
# Scraping
# ==========================================
def fetch_projects():
    try:
        response = requests.get(SCRAPE_URL, headers=HEADERS, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print("[ERROR] Fetch projects:", e)
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    projects = []

    for h2 in soup.find_all("h2", class_="mrg--bt-reset"):
        a = h2.find("a")
        if a:
            projects.append({
                "title": a.text.strip(),
                "link": a["href"]
            })

    return projects

def filter_projects(projects):
    return [
        p for p in projects
        if any(k.lower() in p["title"].lower() for k in KEYWORDS)
    ]

def fetch_project_description(url):
    time.sleep(REQUEST_DELAY)
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        tag = (
            soup.find("div", id="project-brief-panel") or
            soup.find("div", class_="text-wrapper-div")
        )

        return tag.text.strip() if tag else ""

    except Exception as e:
        print("[ERROR] Fetch description:", e)
        return ""

# ==========================================
# State
# ==========================================
def is_new_project(link):
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            if f.read().strip() == link:
                return False

    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        f.write(link)

    return True

# ==========================================
# AI
# ==========================================
def analyze_with_gemini(description):
    prompt = f"""
أنت محلل بيانات محترف.
استخرج:
1. أهم 3 متطلبات
2. عرض احترافي قصير

الوصف:
{description}
"""

    try:
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-preview",
            contents=prompt,
        )
        return response.text.strip()

    except Exception as e:
        print("[ERROR] Gemini:", e)
        return "فشل التحليل."

# ==========================================
# Telegram (FIXED)
# ==========================================
def send_telegram_message(title, link, analysis):

    # تقليل الطول لتجنب رفض Telegram
    analysis = analysis[:3000]

    message = (
        f"🎯 مشروع جديد:\n{title}\n\n"
        f"🔗 {link}\n\n"
        f"🤖 تحليل:\n{analysis}"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
        # شيلنا Markdown لتجنب errors
    }

    try:
        response = requests.post(url, data=payload, timeout=10)

        # 🔥 أهم سطر للتشخيص
        print("Telegram response:", response.text)

        if response.status_code == 200:
            print("[SUCCESS] Message sent.")
        else:
            print("[ERROR] Status:", response.status_code)

    except Exception as e:
        print("[ERROR] Telegram:", e)

# ==========================================
# Main
# ==========================================
def run():
    print("[INFO] Starting...")

    projects = fetch_projects()
    if not projects:
        print("[INFO] No projects.")
        return

    matched = filter_projects(projects)

    print(f"[INFO] Found {len(matched)} project(s)")

    for project in matched:
        if not is_new_project(project["link"]):
            continue

        print("[NEW]", project["title"])

        description = fetch_project_description(project["link"])

        analysis = analyze_with_gemini(description) if description else "لا يوجد وصف."

        send_telegram_message(project["title"], project["link"], analysis)

        break

    print("[INFO] Done.")

if __name__ == "__main__":
    run()