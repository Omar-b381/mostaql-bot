import os
import time
import requests
from bs4 import BeautifulSoup
from google import genai  # <-- Updated to the correct new SDK import

from dotenv import load_dotenv  # <-- أضف هذا السطر

# تحميل المتغيرات من ملف .env
load_dotenv()  # <-- وأضف هذا السطر هنا

# ==========================================
# Configuration — set via environment vars
# ==========================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY     = os.getenv("GEMINI_API_KEY")

KEYWORDS = [
    "تحليل بيانات", "محلل بيانات", "احصاء", "إحصاء", "إحصائي",
    "Data Analysis", "Data Analyst", "Data Science", "Excel", "إكسيل",
    "اكسيل", "Power BI", "باور بي آي", "Tableau", "Python", "بايثون",
    "SQL", "قواعد بيانات", "Dashboard", "داشبورد", "لوحة تحكم","محلل","تقارير","تقرير","تسويق","تسويق رقمي","تحليل تسويقي","cv","سيرة ذاتية","سير ذاتية","سيرتي الذاتية","سيرتي الذاتيه","سيرتي","سيرتي الذاتيه","سيرتي الذاتية","سيرتي الذاتيه","سيرتي الذاتية"
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/91.0.4472.124 Safari/537.36"
    )
}

SCRAPE_URL    = "https://mostaql.com/projects?keyword=بيانات"
SEEN_FILE     = "last_project.txt"
REQUEST_DELAY = 3  # seconds between detail requests

# ==========================================
# Setup Gemini (new google-genai SDK)
# ==========================================
client = genai.Client(api_key=GEMINI_API_KEY)


# ==========================================
# Scraping
# ==========================================
def fetch_projects() -> list[dict]:
    """Fetch project list from Mostaql and return title/link pairs."""
    try:
        response = requests.get(SCRAPE_URL, headers=HEADERS, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"[ERROR] Failed to fetch project list: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    projects = []
    for h2 in soup.find_all("h2", class_="mrg--bt-reset"):
        a = h2.find("a")
        if a:
            projects.append({"title": a.text.strip(), "link": a["href"]})
    return projects


def filter_projects(projects: list[dict]) -> list[dict]:
    """Keep only projects whose title contains at least one keyword."""
    return [
        p for p in projects
        if any(k.lower() in p["title"].lower() for k in KEYWORDS)
    ]


def fetch_project_description(url: str) -> str:
    """Return the project description text, or an empty string on failure."""
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
    except requests.RequestException as e:
        print(f"[ERROR] Failed to fetch project details: {e}")
        return ""


# ==========================================
# State Tracking
# ==========================================
def is_new_project(link: str) -> bool:
    """Return True if this project link has not been seen before, and save it."""
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            if f.read().strip() == link:
                return False
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        f.write(link)
    return True


# ==========================================
# AI Analysis
# ==========================================
def analyze_with_gemini(description: str) -> str:
    """Use Gemini to extract requirements and draft a proposal."""
    prompt = f"""
أنت محلل بيانات محترف وخبير في العمل الحر على منصة مستقل.
قم بقراءة وصف المشروع التالي واستخرج لي:
1. أهم 3 متطلبات يريدها العميل بوضوح.
2. اكتب مسودة عرض (Proposal) احترافية، قصيرة، ومقنعة جداً للتقديم على هذا المشروع.

وصف المشروع:
{description}
"""
    try:
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-preview",
            contents=prompt,
        )
        return response.text.strip()
    except Exception as e:
        print(f"[ERROR] Gemini analysis failed: {e}")
        return "لم يتمكن الذكاء الاصطناعي من تحليل الوصف بسبب خطأ تقني."


# ==========================================
# Telegram Notification
# ==========================================
def send_telegram_message(title: str, link: str, analysis: str) -> None:
    """Send a formatted message to the configured Telegram chat."""
    message = (
        f"🎯 *مشروع جديد: {title}*\n\n"
        f"🔗 *الرابط:* {link}\n\n"
        f"🤖 *تحليل وتوصية Gemini:*\n{analysis}"
    )
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
    }
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data=payload,
            timeout=10,
        )
        print("[INFO] Message sent to Telegram successfully.")
    except requests.RequestException as e:
        print(f"[ERROR] Telegram send failed: {e}")


# ==========================================
# Main Workflow
# ==========================================
def run() -> None:
    """Main entry point: fetch, filter, analyze, and notify."""
    print("[INFO] Starting Mostaql project scanner...")

    projects = fetch_projects()
    if not projects:
        print("[INFO] No projects found on the page.")
        return

    matched = filter_projects(projects)
    if not matched:
        print("[INFO] No projects matched the keyword list.")
        return

    print(f"[INFO] Found {len(matched)} matching project(s). Checking for new ones...")

    for project in matched:
        if not is_new_project(project["link"]):
            print("[INFO] No new matching project since last run.")
            break

        print(f"[INFO] 🚀 New project: {project['title']}")

        description = fetch_project_description(project["link"])
        analysis = (
            analyze_with_gemini(description)
            if description
            else "لم أتمكن من جلب الوصف الداخلي لتحليله."
        )

        send_telegram_message(project["title"], project["link"], analysis)
        break  # process only the first new match per run

    print("[INFO] Scan complete.")


if __name__ == "__main__":
    run()