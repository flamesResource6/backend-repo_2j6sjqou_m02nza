import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from schemas import Reservation as ReservationSchema
from database import create_document, get_documents, db

app = FastAPI(title="Étoile Noire API", description="Luxury restaurant backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Welcome to Étoile Noire Backend"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    return response


# ----------------------- Reservations -----------------------

class ReservationCreate(BaseModel):
    name: str = Field(...)
    phone: str = Field(...)
    date: str = Field(..., description="YYYY-MM-DD")
    time: str = Field(..., description="HH:MM 24h")
    party_size: int = Field(..., ge=1, le=20)
    occasion: Optional[str] = None
    notes: Optional[str] = None


@app.post("/api/reservations")
def create_reservation(payload: ReservationCreate):
    try:
        # Validate against canonical schema
        reservation = ReservationSchema(**payload.model_dump())
        inserted_id = create_document("reservation", reservation)
        return {"status": "ok", "id": inserted_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/reservations")
def list_reservations(limit: int = 20):
    try:
        docs = get_documents("reservation", {}, limit)
        # Convert ObjectId to str if present
        for d in docs:
            if "_id" in d:
                d["id"] = str(d.pop("_id"))
        return {"items": docs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ----------------------- AI Chat ----------------------------

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]

class ChatResponse(BaseModel):
    reply: str
    suggestions: List[str] = []
    maybe_reservation: Optional[Dict[str, Any]] = None


def simple_recommender(text: str) -> ChatResponse:
    t = text.lower()
    suggestions: List[str] = []
    reply = ""

    if any(k in t for k in ["wine", "pairing", "sommelier"]):
        suggestions.append("Grand Cru Burgundy 2015")
        suggestions.append("Vintage Champagne Brut 2008")
        reply = "Our sommelier recommends a Grand Cru Burgundy with rich mains or a vintage Champagne to open the evening."
    if any(k in t for k in ["steak", "beef", "wagyu"]):
        suggestions.append("A5 Miyazaki Wagyu with black truffle jus")
        reply = (reply + " ").strip() + " Our signature A5 Wagyu is seared over binchotan and finished with truffle jus."
    if any(k in t for k in ["vegan", "vegetarian"]):
        suggestions.append("Charred Romanesco with almond velouté")
        reply = (reply + " ").strip() + " We offer refined plant-forward courses like Charred Romanesco with almond velouté."
    if any(k in t for k in ["dessert", "sweet", "chocolate"]):
        suggestions.append("72% Dark Chocolate Marquis with gold leaf")
        reply = (reply + " ").strip() + " For dessert, the Dark Chocolate Marquis adorned with gold leaf is exquisite."

    # Reservation detection
    maybe_reservation = None
    if any(k in t for k in ["book", "reserve", "table", "reservation"]):
        reply = (reply + " ").strip() + " I can book a table for you. Please share date, time, and party size."

    if reply == "":
        reply = (
            "Welcome to Étoile Noire. Tell me what you enjoy (steak, vegan, wine) or say 'reserve' to book a table."
        )

    return ChatResponse(reply=reply, suggestions=suggestions, maybe_reservation=maybe_reservation)


@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest):
    if not req.messages:
        raise HTTPException(status_code=400, detail="No messages provided")
    user_texts = [m.content for m in req.messages if m.role == "user"]
    last_text = user_texts[-1] if user_texts else req.messages[-1].content
    result = simple_recommender(last_text)
    return result


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
