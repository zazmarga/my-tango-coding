from sqlalchemy import Column, Integer, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

#
Base = declarative_base()


class DailyTangoCode(Base):
	__tablename__ = "tango_code"

	id = Column(Integer, primary_key=True)
	quote_ua = Column(Text, nullable=False)
	quote_es = Column(Text, nullable=False)
	quote_en = Column(Text, nullable=False)
	code = Column(Text, nullable=False)
	comment_ua = Column(Text)
	comment_es = Column(Text)
	comment_en = Column(Text)


from pydantic import BaseModel
from typing import Optional


class QuoteResponse(BaseModel):
	id: int
	quote_ua: str
	quote_es: str
	quote_en: str
	code: str
	comment_ua: Optional[str] = None   # можна не заповнювати
	comment_es: Optional[str] = None   # можна не заповнювати
	comment_en: Optional[str] = None   # можна не заповнювати

	model_config = {"from_attributes": True}


class QuoteCreate(BaseModel):
	quote_ua: str
	quote_es: str
	quote_en: str
	code: str
	comment_ua: Optional[str] = None   # можна не заповнювати
	comment_es: Optional[str] = None   # можна не заповнювати
	comment_en: Optional[str] = None   # можна не заповнювати


	class Config:
		schema_extra = {
			"example": {
				"quote_ua": "Танго — це коли два серця б'ються в одному ритмі.",
				"quote_es": "El tango es cuando dos corazones laten al mismo ritmo.",
				"quote_en": "Tango is when two hearts beat in the same rhythm.",
				"code": "@app.get(\"/health\")\nasync def health():\n    return {\"status\": \"ok ❤️\"}",
				"comment_ua": "# моя улюблена цитата",
				"comment_es": "# mi frase favorita",
				"comment_en": "# my favourite frase",
			}
		}


class QuoteUpdate(BaseModel):  # Для вхідних даних (оновлення)
	quote_ua: Optional[str] = None
	quote_es: Optional[str] = None
	quote_en: Optional[str] = None
	code: Optional[str] = None
	comment_ua: Optional[str] = None
	comment_es: Optional[str] = None
	comment_en: Optional[str] = None



# Підключення до бази (файл з'явиться автоматично)
engine = create_engine("sqlite:///data/tango.db")
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)