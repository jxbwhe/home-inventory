from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import sessionmaker, Session, relationship, declarative_base
from datetime import datetime
import shutil
import os
import uuid
import http.client
import urllib.parse
import json
import logging
from pydantic import BaseModel
from typing import List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

os.makedirs("data/uploads", exist_ok=True)

# PushPlus Configuration
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN", "")

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
    unit = Column(String, default="个")
    min_quantity = Column(Float, default=0.0)  # 最低库存阈值
    last_purchase_date = Column(DateTime, nullable=True)
    last_usage_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    purchases = relationship("PurchaseDB", back_populates="item", cascade="all, delete-orphan")
    usages = relationship("UsageDB", back_populates="item", cascade="all, delete-orphan")

class PurchaseDB(Base):
    __tablename__ = "purchases"
    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id"))
    date = Column(DateTime, default=datetime.utcnow)
    quantity = Column(Float)
    price = Column(Float)
    unit_price = Column(Float, default=0.0)
    image_url = Column(String, nullable=True)

    item = relationship("ItemDB", back_populates="purchases")

class UsageDB(Base):
    __tablename__ = "usages"
    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id"))
    date = Column(DateTime, default=datetime.utcnow)
    quantity = Column(Float)

    item = relationship("ItemDB", back_populates="usages")

Base.metadata.create_all(bind=engine)

app = FastAPI(title="家庭消耗品管理")
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


# ---- PushPlus Notification ----
def send_pushplus_notification(title: str, content: str):
    """Send notification via PushPlus"""
    if not PUSHPLUS_TOKEN:
        logger.warning("PUSHPLUS_TOKEN not configured, skipping notification")
        return False
    try:
        conn = http.client.HTTPSConnection("www.pushplus.plus")
        encoded_content = urllib.parse.quote(content)
        encoded_title = urllib.parse.quote(title)
        conn.request(
            "GET",
            f"/send?token={PUSHPLUS_TOKEN}&title={encoded_title}&content={encoded_content}"
        )
        res = conn.getresponse()
        data = res.read()
        logger.info(f"PushPlus response: {data.decode('utf-8')}")
        return True
    except Exception as e:
        logger.error(f"PushPlus notification failed: {e}")
        return False


def check_low_inventory(db: Session, specific_item: ItemDB = None):
    """Check inventory levels and send alerts for items below threshold"""
    if specific_item:
        items_to_check = [specific_item]
    else:
        items_to_check = db.query(ItemDB).filter(ItemDB.min_quantity > 0).all()

    low_items = []
    for item in items_to_check:
        if item.min_quantity > 0 and item.current_quantity <= item.min_quantity:
            low_items.append(item)

    if low_items:
        content_lines = ["以下物品库存不足，请及时补货：\n"]
        for item in low_items:
            content_lines.append(
                f"📦 {item.name}：当前 {item.current_quantity} {item.unit}，"
                f"阈值 {item.min_quantity} {item.unit}"
            )
        content = "\n".join(content_lines)
        send_pushplus_notification("⚠️ 家庭消耗品库存不足提醒", content)

    return low_items


def save_upload_file(upload_file: UploadFile) -> str:
    """Save uploaded file and return URL path"""
    ext = os.path.splitext(upload_file.filename)[1] if upload_file.filename else ".jpg"
    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_location = f"data/uploads/{unique_name}"
    with open(file_location, "wb+") as f:
        shutil.copyfileobj(upload_file.file, f)
    return f"/uploads/{unique_name}"


# ---- Routes ----

@app.post("/api/items")
async def create_item(
    name: str = Form(...),
    description: str = Form(""),
    unit: str = Form("个"),
    min_quantity: float = Form(0.0),
    image: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    image_url = None
    if image and image.filename:
        image_url = save_upload_file(image)

    db_item = ItemDB(
        name=name,
        description=description,
        unit=unit,
        image_url=image_url,
        min_quantity=min_quantity,
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return {"message": "物品添加成功", "id": db_item.id}


@app.get("/api/items")
def get_items(db: Session = Depends(get_db)):
    items = db.query(ItemDB).all()
    result = []
    for item in items:
        total_cost = sum(p.price for p in item.purchases)
        days = (datetime.utcnow() - item.created_at).days
        days = days if days > 0 else 1
        daily_cost = total_cost / days

        # Get latest unit price
        latest_purchase = sorted(item.purchases, key=lambda p: p.date, reverse=True)
        latest_unit_price = latest_purchase[0].unit_price if latest_purchase else 0

        is_low = item.min_quantity > 0 and item.current_quantity <= item.min_quantity

        item_data = {
            "id": item.id,
            "name": item.name,
            "description": item.description,
            "image_url": item.image_url,
            "current_quantity": item.current_quantity,
            "unit": item.unit,
            "min_quantity": item.min_quantity,
            "daily_cost": round(daily_cost, 2),
            "total_cost": round(total_cost, 2),
            "latest_unit_price": round(latest_unit_price, 2),
            "last_purchase_date": item.last_purchase_date.strftime("%Y-%m-%d %H:%M") if item.last_purchase_date else None,
            "last_usage_date": item.last_usage_date.strftime("%Y-%m-%d %H:%M") if item.last_usage_date else None,
            "is_low": is_low,
            "created_at": item.created_at.strftime("%Y-%m-%d %H:%M"),
        }
        result.append(item_data)
    return result


@app.get("/api/items/{item_id}")
def get_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(ItemDB).filter(ItemDB.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="物品不存在")

    return {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "image_url": item.image_url,
        "current_quantity": item.current_quantity,
        "unit": item.unit,
        "min_quantity": item.min_quantity,
        "last_purchase_date": item.last_purchase_date.strftime("%Y-%m-%d %H:%M") if item.last_purchase_date else None,
        "last_usage_date": item.last_usage_date.strftime("%Y-%m-%d %H:%M") if item.last_usage_date else None,
    }


@app.put("/api/items/{item_id}")
async def update_item(
    item_id: int,
    name: str = Form(None),
    description: str = Form(None),
    unit: str = Form(None),
    min_quantity: float = Form(None),
    current_quantity: float = Form(None),
    image: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    db_item = db.query(ItemDB).filter(ItemDB.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="物品不存在")

    if name is not None:
        db_item.name = name
    if description is not None:
        db_item.description = description
    if unit is not None:
        db_item.unit = unit
    if min_quantity is not None:
        db_item.min_quantity = min_quantity
    if current_quantity is not None:
        db_item.current_quantity = current_quantity
    if image and image.filename:
        db_item.image_url = save_upload_file(image)

    db.commit()
    return {"message": "物品更新成功"}


@app.delete("/api/items/{item_id}")
def delete_item(item_id: int, db: Session = Depends(get_db)):
    db_item = db.query(ItemDB).filter(ItemDB.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="物品不存在")

    db.delete(db_item)
    db.commit()
    return {"message": "物品已删除"}


@app.post("/api/purchases")
async def add_purchase(
    item_id: int = Form(...),
    quantity: float = Form(...),
    price: float = Form(...),
    image: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    db_item = db.query(ItemDB).filter(ItemDB.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="物品不存在")

    image_url = None
    if image and image.filename:
        image_url = save_upload_file(image)

    unit_price = round(price / quantity, 2) if quantity > 0 else 0
    now = datetime.utcnow()

    db_purchase = PurchaseDB(
        item_id=item_id,
        quantity=quantity,
        price=price,
        unit_price=unit_price,
        image_url=image_url,
        date=now,
    )
    db_item.current_quantity += quantity
    db_item.last_purchase_date = now

    db.add(db_purchase)
    db.commit()
    return {"message": "购买记录已添加"}


@app.get("/api/items/{item_id}/purchases")
def get_item_purchases(item_id: int, db: Session = Depends(get_db)):
    db_item = db.query(ItemDB).filter(ItemDB.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="物品不存在")

    purchases = db.query(PurchaseDB).filter(
        PurchaseDB.item_id == item_id
    ).order_by(PurchaseDB.date.desc()).all()

    return [
        {
            "id": p.id,
            "date": p.date.strftime("%Y-%m-%d %H:%M"),
            "quantity": p.quantity,
            "price": round(p.price, 2),
            "unit_price": round(p.unit_price, 2),
            "image_url": p.image_url,
        }
        for p in purchases
    ]


@app.post("/api/usages")
async def add_usage(
    item_id: int = Form(...),
    quantity: float = Form(...),
    db: Session = Depends(get_db)
):
    db_item = db.query(ItemDB).filter(ItemDB.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="物品不存在")

    if db_item.current_quantity < quantity:
        raise HTTPException(status_code=400, detail="库存不足")

    now = datetime.utcnow()
    db_usage = UsageDB(
        item_id=item_id,
        quantity=quantity,
        date=now,
    )
    db_item.current_quantity -= quantity
    db_item.last_usage_date = now

    db.add(db_usage)
    db.commit()

    # Check inventory after usage
    check_low_inventory(db, db_item)

    return {"message": "使用记录已添加"}


@app.get("/api/dashboard")
def get_dashboard(db: Session = Depends(get_db)):
    items = db.query(ItemDB).all()
    total_inventory_value = 0
    total_daily_cost = 0
    low_stock_items = []

    for item in items:
        total_cost = sum(p.price for p in item.purchases)
        total_qty_bought = sum(p.quantity for p in item.purchases)
        avg_price = (total_cost / total_qty_bought) if total_qty_bought > 0 else 0
        total_inventory_value += avg_price * item.current_quantity

        days = (datetime.utcnow() - item.created_at).days
        days = days if days > 0 else 1
        total_daily_cost += total_cost / days

        if item.min_quantity > 0 and item.current_quantity <= item.min_quantity:
            low_stock_items.append({
                "id": item.id,
                "name": item.name,
                "current_quantity": item.current_quantity,
                "min_quantity": item.min_quantity,
                "unit": item.unit,
            })

    return {
        "total_items": len(items),
        "total_value": round(total_inventory_value, 2),
        "total_daily_cost": round(total_daily_cost, 2),
        "low_stock_count": len(low_stock_items),
        "low_stock_items": low_stock_items,
    }


@app.post("/api/check-inventory")
def manual_check_inventory(db: Session = Depends(get_db)):
    """手动触发库存检查并推送通知"""
    low_items = check_low_inventory(db)
    if low_items:
        return {
            "message": f"发现 {len(low_items)} 个物品库存不足，已推送通知",
            "low_items": [{"name": i.name, "current": i.current_quantity, "threshold": i.min_quantity} for i in low_items]
        }
    return {"message": "所有物品库存充足", "low_items": []}


app.mount("/", StaticFiles(directory="app/static", html=True), name="static")