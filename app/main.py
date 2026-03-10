from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import sessionmaker, Session, relationship, declarative_base
from datetime import datetime
import shutil
import os
from pydantic import BaseModel
from typing import List, Optional

os.makedirs("data/uploads", exist_ok=True)

# Database Setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./data/inventory.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Models
class ItemDB(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String, nullable=True)
    image_url = Column(String, nullable=True)
    current_quantity = Column(Float, default=0.0)
    unit = Column(String, default="pcs")
    created_at = Column(DateTime, default=datetime.utcnow)

    purchases = relationship("PurchaseDB", back_populates="item")
    usages = relationship("UsageDB", back_populates="item")

class PurchaseDB(Base):
    __tablename__ = "purchases"
    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id"))
    date = Column(DateTime, default=datetime.utcnow)
    quantity = Column(Float)
    price = Column(Float)
    
    item = relationship("ItemDB", back_populates="purchases")

class UsageDB(Base):
    __tablename__ = "usages"
    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id"))
    date = Column(DateTime, default=datetime.utcnow)
    quantity = Column(Float)
    
    item = relationship("ItemDB", back_populates="usages")

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Home Inventory API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory="data/uploads"), name="uploads")

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pydantic Schemas
class PurchaseCreate(BaseModel):
    item_id: int
    quantity: float
    price: float
    date: Optional[datetime] = None

class UsageCreate(BaseModel):
    item_id: int
    quantity: float
    date: Optional[datetime] = None

# Routes
@app.post("/api/items")
async def create_item(
    name: str = Form(...),
    description: str = Form(""),
    unit: str = Form("pcs"),
    image: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    image_url = None
    if image and image.filename:
        file_location = f"data/uploads/{image.filename}"
        with open(file_location, "wb+") as file_object:
            shutil.copyfileobj(image.file, file_object)
        image_url = f"/uploads/{image.filename}"

    db_item = ItemDB(name=name, description=description, unit=unit, image_url=image_url)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

@app.get("/api/items")
def get_items(db: Session = Depends(get_db)):
    items = db.query(ItemDB).all()
    result = []
    for item in items:
        total_cost = sum(p.price for p in item.purchases)
        days = (datetime.utcnow() - item.created_at).days
        days = days if days > 0 else 1
        daily_cost = total_cost / days
        
        item_data = {
            "id": item.id,
            "name": item.name,
            "description": item.description,
            "image_url": item.image_url,
            "current_quantity": item.current_quantity,
            "unit": item.unit,
            "daily_cost": round(daily_cost, 2),
            "total_cost": total_cost,
        }
        result.append(item_data)
    return result

@app.post("/api/purchases")
def add_purchase(purchase: PurchaseCreate, db: Session = Depends(get_db)):
    db_item = db.query(ItemDB).filter(ItemDB.id == purchase.item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    db_purchase = PurchaseDB(
        item_id=purchase.item_id,
        quantity=purchase.quantity,
        price=purchase.price,
        date=purchase.date or datetime.utcnow()
    )
    db_item.current_quantity += purchase.quantity
    
    db.add(db_purchase)
    db.commit()
    return {"message": "Purchase added successfully"}

@app.post("/api/usages")
def add_usage(usage: UsageCreate, db: Session = Depends(get_db)):
    db_item = db.query(ItemDB).filter(ItemDB.id == usage.item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    if db_item.current_quantity < usage.quantity:
        raise HTTPException(status_code=400, detail="Not enough quantity")
        
    db_usage = UsageDB(
        item_id=usage.item_id,
        quantity=usage.quantity,
        date=usage.date or datetime.utcnow()
    )
    db_item.current_quantity -= usage.quantity
    
    db.add(db_usage)
    db.commit()
    return {"message": "Usage recorded successfully"}

@app.get("/api/dashboard")
def get_dashboard(db: Session = Depends(get_db)):
    items = db.query(ItemDB).all()
    total_inventory_value = 0
    total_daily_cost = 0
    
    for item in items:
        total_cost = sum(p.price for p in item.purchases)
        total_qty_bought = sum(p.quantity for p in item.purchases)
        avg_price = (total_cost / total_qty_bought) if total_qty_bought > 0 else 0
        total_inventory_value += avg_price * item.current_quantity
        
        days = (datetime.utcnow() - item.created_at).days
        days = days if days > 0 else 1
        total_daily_cost += total_cost / days
        
    return {
        "total_items": len(items),
        "total_value": round(total_inventory_value, 2),
        "total_daily_cost": round(total_daily_cost, 2)
    }

app.mount("/", StaticFiles(directory="app/static", html=True), name="static")