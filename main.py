import random
import httpx, json
from typing import Optional
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Depends, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from bs4 import BeautifulSoup

import resend

from sqlalchemy.orm import Session
from models import SessionLocal, DailyTangoCode, QuoteCreate, QuoteResponse, QuoteUpdate

from dotenv import load_dotenv
import os

load_dotenv()


# ====================== СЕКРЕТИ ======================
resend.api_key = os.getenv("RESEND_API_KEY")          # для листів # https://resend.com → email-messages
SECRET_API_KEY = os.getenv("SECRET_API_KEY")          # твій особистий ключ (не в коді!)

if not SECRET_API_KEY:
    raise RuntimeError("Встанови SECRET_API_KEY в .env!")


# ====================== FastAPI ======================
app = FastAPI(title="ZazMarga.xyz Tango API", version="1.0")


# Health без обмежень
@app.get("/health", include_in_schema=False)
async def health():
    return {"status": "ok"}


app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://zazmarga.xyz", "http://localhost:3000", "http://localhost:63342"],  # тільки твій сайт
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ====================== Захист API-ключа ======================
from fastapi.security import APIKeyHeader
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(x_api_key: str = Depends(api_key_header)):
    if not SECRET_API_KEY:  # на випадок локального тесту
        return True
    if x_api_key != SECRET_API_KEY:
        raise HTTPException(status_code=401, detail="Невірний API ключ")
    return x_api_key


# ====================== База даних ======================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



# ====================== HTTP-клієнт для hoy-milonga ======================
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
]

client = httpx.AsyncClient(
    timeout=30.0,
    headers={"User-Agent": random.choice(USER_AGENTS)},
    limits=httpx.Limits(max_connections=20),
)


BA_OFFSET = timedelta(hours=-3)
_cached_count = None
_cached_time = None


async def get_milongas_running_right_now():
    global _cached_count, _cached_time

    url = "https://www.hoy-milonga.com/buenos-aires/es/milongas"

    now_ba = datetime.now(timezone.utc) + BA_OFFSET

    if _cached_time is None or datetime.now(timezone.utc) - _cached_time > timedelta(minutes=30):
        try:
            r = await client.get(url)
            r.raise_for_status()

            soup = BeautifulSoup(r.text, "html.parser")
            active = []

            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(script.string)
                    if data.get("@type") != "DanceEvent":
                        continue

                    # in this moment:
                    start = datetime.fromisoformat(data["startDate"])

                    # Перевірка: мілонга йде today
                    if start.date() == now_ba.date():
                        active.append(data["name"])
                except:
                    continue
            _cached_count = len(active)
            _cached_time = datetime.now(timezone.utc)
        except httpx.ConnectTimeout:
            pass
        except Exception as e:
            print("Parsing error:", e)

    return _cached_count if _cached_count is not None else 0


#========        front + back   ===========#
# Віддаємо картинки
app.mount("/images", StaticFiles(directory="images"), name="images")

# Віддаємо index.html як фронт
@app.get("/")
def read_index():
    return FileResponse("index.html")

# ====================== Ендпоінти ======================
@app.get("/api/milongas")
async def get_milongas():
    count = await get_milongas_running_right_now()
    return {
        "milongas_now": count
    }


# 1. Отримати випадкову цитату
@app.get("/api/random_quote")
async def get_random_quote(db: Session = Depends(get_db)) -> QuoteResponse:
    count = db.query(DailyTangoCode).count()
    if count == 0:
        raise HTTPException(404, "Цитати закінчились, додай нові!")
    random_quote = db.query(DailyTangoCode).offset(random.randint(0, count-1)).first()
    return QuoteResponse.model_validate(random_quote)


# 2. Додати нову цитату
@app.post("/api/add-quote")
async def add_quote(quote: QuoteCreate, db: Session = Depends(get_db), _: str = Depends(verify_api_key)):
    new_quote = DailyTangoCode(**quote.dict())
    db.add(new_quote)
    db.commit()
    return {"status": "Додано! Тепер цитат: " + str(db.query(DailyTangoCode).count())}


# 2. Update цитату
@app.put("/api/update-quote/{quote_id}")
async def update_quote(
        quote_id: int,
        updated_quote: QuoteUpdate,
        db: Session = Depends(get_db),
        _: str = Depends(verify_api_key)
) -> QuoteResponse:
    # Шукаємо цитату в базі
    quote = db.query(DailyTangoCode).filter(DailyTangoCode.id == quote_id).first()

    if quote is None:
        raise HTTPException(status_code=404, detail="Цитата не знайдена")

    # Оновлюємо ТІЛЬКИ те, що прийшло в JSON!
    update_data = updated_quote.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(quote, key, value)

    db.commit()
    db.refresh(quote)

    return QuoteResponse.model_validate(quote)


@app.post("/api/send-message")
async def send_message(
    name: str = Form(...),
    email: str = Form(...),
    company: str = Form(None),
    location: str = Form(...),
    preferred_time: str = Form(...),
    message: Optional[str] = Form(None)
):
    try:
        resend.Emails.send({
            "from": "MyTangoCoding <onboarding@resend.dev>",
            "to": "zazmargo@gmail.com",
            "subject": f"Нове запрошення на співбесіду від {name} ({location})",
            "html": f"""
                <h2>Привіт! Хтось хоче з тобою поспілкуватися</h2>
                <p><strong>Ім'я:</strong> {name}</p>
                <p><strong>Email відправника:</strong> {email}</p>
                <p><strong>Компанія відправника:</strong> {company}</p>
                <p><strong>Місцезнаходження: </strong> {location}</p>
                <p><strong>Запропонована дата та час: </strong> {preferred_time}</p>                
                <p><strong>Повідомлення:</strong><br>{message.replace(chr(10), '<br>')}</p>
                <hr>
                <small>Надіслано з MyTangoCoding.dev</small>
            """
        })
        return {"status": "ok", "message": "Лист відправлено!"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
