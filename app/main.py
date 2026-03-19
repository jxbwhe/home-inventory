from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Header, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime, Boolean, Text
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

# Database Setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./data/inventory.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

TIME_FMT = "%Y-%m-%d %H:%M:%S"


# ===================== Models =====================

class FamilyDB(Base):
    __tablename__ = "families"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    items = relationship("ItemDB", back_populates="family", cascade="all, delete-orphan")


class ItemDB(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String, nullable=True)
    image_url = Column(String, nullable=True)
    current_quantity = Column(Float, default=0.0)
    unit = Column(String, default="个")
    min_quantity = Column(Float, default=0.0)
    last_purchase_date = Column(DateTime, nullable=True)
    last_usage_date = Column(DateTime, nullable=True)
    family_id = Column(Integer, ForeignKey("families.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    family = relationship("FamilyDB", back_populates="items")
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


class NotifyChannelDB(Base):
    __tablename__ = "notify_channels"
    id = Column(Integer, primary_key=True, index=True)
    channel_type = Column(String, default="pushplus")  # pushplus / webhook / ...
    name = Column(String)
    config = Column(Text, default="{}")  # JSON: {"token": "xxx"} etc.
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ApiTokenDB(Base):
    __tablename__ = "api_tokens"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    token = Column(String, unique=True, index=True)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


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


# ===================== Dependencies =====================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_api_token(x_api_token: str = Header(...), db: Session = Depends(get_db)):
    """Verify external API token"""
    token_record = db.query(ApiTokenDB).filter(
        ApiTokenDB.token == x_api_token,
        ApiTokenDB.enabled == True
    ).first()
    if not token_record:
        raise HTTPException(status_code=401, detail="无效的 API Token")
    return token_record


# ===================== Notification Module =====================

def _send_pushplus(token: str, title: str, content: str) -> bool:
    try:
        conn = http.client.HTTPSConnection("www.pushplus.plus")
        encoded_content = urllib.parse.quote(content)
        encoded_title = urllib.parse.quote(title)
        conn.request("GET", f"/send?token={token}&title={encoded_title}&content={encoded_content}")
        res = conn.getresponse()
        data = res.read()
        logger.info(f"PushPlus response: {data.decode('utf-8')}")
        return True
    except Exception as e:
        logger.error(f"PushPlus failed: {e}")
        return False


def send_notification(db: Session, title: str, content: str):
    """Send notification through all enabled channels"""
    channels = db.query(NotifyChannelDB).filter(NotifyChannelDB.enabled == True).all()
    if not channels:
        logger.warning("No enabled notification channels")
        return False
    success = False
    for ch in channels:
        try:
            cfg = json.loads(ch.config) if ch.config else {}
        except json.JSONDecodeError:
            cfg = {}
        if ch.channel_type == "pushplus":
            token = cfg.get("token", "")
            if token and _send_pushplus(token, title, content):
                success = True
        # Future: add more channel types here
    return success


def check_low_inventory(db: Session, specific_item: ItemDB = None):
    if specific_item:
        items_to_check = [specific_item]
    else:
        items_to_check = db.query(ItemDB).filter(ItemDB.min_quantity > 0).all()

    low_items = []
    for item in items_to_check:
        if item.min_quantity > 0 and item.current_quantity <= item.min_quantity:
            low_items.append(item)

    if low_items:
        lines = ["以下物品库存不足，请及时补货：\n"]
        for item in low_items:
            family_name = item.family.name if item.family else "未分组"
            lines.append(f"📦 [{family_name}] {item.name}：当前 {item.current_quantity} {item.unit}，阈值 {item.min_quantity} {item.unit}")
        send_notification(db, "⚠️ 家庭消耗品库存不足提醒", "\n".join(lines))

    return low_items


def save_upload_file(upload_file: UploadFile) -> str:
    ext = os.path.splitext(upload_file.filename)[1] if upload_file.filename else ".jpg"
    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_location = f"data/uploads/{unique_name}"
    with open(file_location, "wb+") as f:
        shutil.copyfileobj(upload_file.file, f)
    return f"/uploads/{unique_name}"


def _item_to_dict(item: ItemDB) -> dict:
    total_cost = sum(p.price for p in item.purchases)
    days = (datetime.utcnow() - item.created_at).days
    days = days if days > 0 else 1
    daily_cost = total_cost / days
    latest_purchase = sorted(item.purchases, key=lambda p: p.date, reverse=True)
    latest_unit_price = latest_purchase[0].unit_price if latest_purchase else 0
    is_low = item.min_quantity > 0 and item.current_quantity <= item.min_quantity
    return {
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
        "last_purchase_date": item.last_purchase_date.strftime(TIME_FMT) if item.last_purchase_date else None,
        "last_usage_date": item.last_usage_date.strftime(TIME_FMT) if item.last_usage_date else None,
        "is_low": is_low,
        "family_id": item.family_id,
        "family_name": item.family.name if item.family else None,
        "created_at": item.created_at.strftime(TIME_FMT),
    }


# ===================== Family Routes =====================

@app.post("/api/families")
def create_family(name: str = Form(...), db: Session = Depends(get_db)):
    f = FamilyDB(name=name)
    db.add(f)
    db.commit()
    db.refresh(f)
    return {"message": "家庭创建成功", "id": f.id, "name": f.name}


@app.get("/api/families")
def get_families(db: Session = Depends(get_db)):
    families = db.query(FamilyDB).order_by(FamilyDB.id).all()
    return [{"id": f.id, "name": f.name, "item_count": len(f.items), "created_at": f.created_at.strftime(TIME_FMT)} for f in families]


@app.put("/api/families/{family_id}")
def update_family(family_id: int, name: str = Form(...), db: Session = Depends(get_db)):
    f = db.query(FamilyDB).filter(FamilyDB.id == family_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="家庭不存在")
    f.name = name
    db.commit()
    return {"message": "家庭更新成功"}


@app.delete("/api/families/{family_id}")
def delete_family(family_id: int, db: Session = Depends(get_db)):
    f = db.query(FamilyDB).filter(FamilyDB.id == family_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="家庭不存在")
    db.delete(f)
    db.commit()
    return {"message": "家庭已删除"}


# ===================== Item Routes =====================

@app.post("/api/items")
async def create_item(
    name: str = Form(...),
    description: str = Form(""),
    unit: str = Form("个"),
    min_quantity: float = Form(0.0),
    family_id: int = Form(None),
    image: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    image_url = None
    if image and image.filename:
        image_url = save_upload_file(image)
    db_item = ItemDB(name=name, description=description, unit=unit, image_url=image_url,
                     min_quantity=min_quantity, family_id=family_id if family_id else None)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return {"message": "物品添加成功", "id": db_item.id}


@app.get("/api/items")
def get_items(family_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(ItemDB)
    if family_id is not None:
        q = q.filter(ItemDB.family_id == family_id)
    items = q.all()
    return [_item_to_dict(item) for item in items]


@app.get("/api/items/{item_id}")
def get_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(ItemDB).filter(ItemDB.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="物品不存在")
    return {
        "id": item.id, "name": item.name, "description": item.description,
        "image_url": item.image_url, "current_quantity": item.current_quantity,
        "unit": item.unit, "min_quantity": item.min_quantity, "family_id": item.family_id,
        "last_purchase_date": item.last_purchase_date.strftime(TIME_FMT) if item.last_purchase_date else None,
        "last_usage_date": item.last_usage_date.strftime(TIME_FMT) if item.last_usage_date else None,
    }


@app.put("/api/items/{item_id}")
async def update_item(
    item_id: int,
    name: str = Form(None), description: str = Form(None), unit: str = Form(None),
    min_quantity: float = Form(None), current_quantity: float = Form(None),
    family_id: int = Form(None),
    image: UploadFile = File(None), db: Session = Depends(get_db)
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
    if family_id is not None:
        db_item.family_id = family_id if family_id > 0 else None
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


# ===================== Purchase Routes =====================

@app.post("/api/purchases")
async def add_purchase(
    item_id: int = Form(...), quantity: float = Form(...), price: float = Form(...),
    image: UploadFile = File(None), db: Session = Depends(get_db)
):
    db_item = db.query(ItemDB).filter(ItemDB.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="物品不存在")
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="购买数量必须大于 0")
    if price < 0:
        raise HTTPException(status_code=400, detail="购买价格不能为负数")
    image_url = None
    if image and image.filename:
        image_url = save_upload_file(image)
    unit_price = round(price / quantity, 2)
    now = datetime.utcnow()
    db_purchase = PurchaseDB(item_id=item_id, quantity=quantity, price=price,
                             unit_price=unit_price, image_url=image_url, date=now)
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
    purchases = db.query(PurchaseDB).filter(PurchaseDB.item_id == item_id).order_by(PurchaseDB.date.desc()).all()
    return [{"id": p.id, "date": p.date.strftime(TIME_FMT), "quantity": p.quantity,
             "price": round(p.price, 2), "unit_price": round(p.unit_price, 2), "image_url": p.image_url} for p in purchases]


# ===================== Usage Routes =====================

@app.post("/api/usages")
async def add_usage(item_id: int = Form(...), quantity: float = Form(...), db: Session = Depends(get_db)):
    db_item = db.query(ItemDB).filter(ItemDB.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="物品不存在")
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="使用数量必须大于 0")
    if db_item.current_quantity < quantity:
        raise HTTPException(status_code=400, detail="库存不足")
    now = datetime.utcnow()
    db_usage = UsageDB(item_id=item_id, quantity=quantity, date=now)
    db_item.current_quantity -= quantity
    db_item.last_usage_date = now
    db.add(db_usage)
    db.commit()
    check_low_inventory(db, db_item)
    return {"message": "使用记录已添加"}


@app.get("/api/items/{item_id}/usages")
def get_item_usages(item_id: int, db: Session = Depends(get_db)):
    db_item = db.query(ItemDB).filter(ItemDB.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="物品不存在")
    usages = db.query(UsageDB).filter(UsageDB.item_id == item_id).order_by(UsageDB.date.desc()).all()
    return [{"id": u.id, "date": u.date.strftime(TIME_FMT), "quantity": u.quantity} for u in usages]


# ===================== Dashboard =====================

@app.get("/api/dashboard")
def get_dashboard(family_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(ItemDB)
    if family_id is not None:
        q = q.filter(ItemDB.family_id == family_id)
    items = q.all()
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
                "id": item.id, "name": item.name,
                "current_quantity": item.current_quantity,
                "min_quantity": item.min_quantity, "unit": item.unit,
                "family_name": item.family.name if item.family else None,
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
    low_items = check_low_inventory(db)
    if low_items:
        return {"message": f"发现 {len(low_items)} 个物品库存不足，已推送通知",
                "low_items": [{"name": i.name, "current": i.current_quantity, "threshold": i.min_quantity} for i in low_items]}
    return {"message": "所有物品库存充足", "low_items": []}


# ===================== Notify Channel Routes =====================

@app.post("/api/notify-channels")
def create_channel(
    channel_type: str = Form("pushplus"), name: str = Form(...),
    config: str = Form("{}"), db: Session = Depends(get_db)
):
    ch = NotifyChannelDB(channel_type=channel_type, name=name, config=config, enabled=True)
    db.add(ch)
    db.commit()
    db.refresh(ch)
    return {"message": "通知渠道创建成功", "id": ch.id}


@app.get("/api/notify-channels")
def get_channels(db: Session = Depends(get_db)):
    channels = db.query(NotifyChannelDB).order_by(NotifyChannelDB.id).all()
    result = []
    for ch in channels:
        try:
            cfg = json.loads(ch.config) if ch.config else {}
        except json.JSONDecodeError:
            cfg = {}
        # Mask token for security
        masked_cfg = {}
        for k, v in cfg.items():
            if "token" in k.lower() and isinstance(v, str) and len(v) > 6:
                masked_cfg[k] = v[:3] + "***" + v[-3:]
            else:
                masked_cfg[k] = v
        result.append({
            "id": ch.id, "channel_type": ch.channel_type, "name": ch.name,
            "config": masked_cfg, "enabled": ch.enabled,
            "created_at": ch.created_at.strftime(TIME_FMT),
        })
    return result


@app.put("/api/notify-channels/{channel_id}")
def update_channel(
    channel_id: int, name: str = Form(None), config: str = Form(None),
    enabled: bool = Form(None), db: Session = Depends(get_db)
):
    ch = db.query(NotifyChannelDB).filter(NotifyChannelDB.id == channel_id).first()
    if not ch:
        raise HTTPException(status_code=404, detail="通知渠道不存在")
    if name is not None:
        ch.name = name
    if config is not None:
        ch.config = config
    if enabled is not None:
        ch.enabled = enabled
    db.commit()
    return {"message": "通知渠道更新成功"}


@app.delete("/api/notify-channels/{channel_id}")
def delete_channel(channel_id: int, db: Session = Depends(get_db)):
    ch = db.query(NotifyChannelDB).filter(NotifyChannelDB.id == channel_id).first()
    if not ch:
        raise HTTPException(status_code=404, detail="通知渠道不存在")
    db.delete(ch)
    db.commit()
    return {"message": "通知渠道已删除"}


@app.post("/api/notify-channels/{channel_id}/test")
def test_channel(channel_id: int, db: Session = Depends(get_db)):
    ch = db.query(NotifyChannelDB).filter(NotifyChannelDB.id == channel_id).first()
    if not ch:
        raise HTTPException(status_code=404, detail="通知渠道不存在")
    try:
        cfg = json.loads(ch.config) if ch.config else {}
    except json.JSONDecodeError:
        cfg = {}
    success = False
    if ch.channel_type == "pushplus":
        token = cfg.get("token", "")
        if token:
            success = _send_pushplus(token, "🔔 测试通知", "这是一条来自家庭消耗品管理的测试通知。如果你收到了，说明通知渠道配置正确！")
    if success:
        return {"message": "测试通知已发送"}
    raise HTTPException(status_code=400, detail="发送失败，请检查配置")


# ===================== API Token Routes =====================

@app.post("/api/tokens")
def create_token(name: str = Form(...), db: Session = Depends(get_db)):
    token_value = uuid.uuid4().hex
    t = ApiTokenDB(name=name, token=token_value, enabled=True)
    db.add(t)
    db.commit()
    db.refresh(t)
    return {"message": "Token 创建成功", "id": t.id, "token": token_value, "name": name}


@app.get("/api/tokens")
def get_tokens(db: Session = Depends(get_db)):
    tokens = db.query(ApiTokenDB).order_by(ApiTokenDB.id).all()
    return [{"id": t.id, "name": t.name, "token": t.token,
             "enabled": t.enabled, "created_at": t.created_at.strftime(TIME_FMT)} for t in tokens]


@app.delete("/api/tokens/{token_id}")
def delete_token(token_id: int, db: Session = Depends(get_db)):
    t = db.query(ApiTokenDB).filter(ApiTokenDB.id == token_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Token 不存在")
    db.delete(t)
    db.commit()
    return {"message": "Token 已删除"}


# ===================== Open API (Token Auth) =====================

class OpenApiItemCreate(BaseModel):
    name: str
    description: str = ""
    unit: str = "个"
    min_quantity: float = 0.0
    family_id: Optional[int] = None

class OpenApiPurchaseCreate(BaseModel):
    item_id: int
    quantity: float
    price: float

class OpenApiUsageCreate(BaseModel):
    item_id: int
    quantity: float


@app.post("/openapi/items")
def openapi_create_item(data: OpenApiItemCreate, token: ApiTokenDB = Depends(verify_api_token), db: Session = Depends(get_db)):
    db_item = ItemDB(name=data.name, description=data.description, unit=data.unit,
                     min_quantity=data.min_quantity, family_id=data.family_id)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return {"message": "物品添加成功", "id": db_item.id}


@app.get("/openapi/items")
def openapi_get_items(family_id: Optional[int] = None, token: ApiTokenDB = Depends(verify_api_token), db: Session = Depends(get_db)):
    q = db.query(ItemDB)
    if family_id is not None:
        q = q.filter(ItemDB.family_id == family_id)
    return [_item_to_dict(item) for item in q.all()]


@app.post("/openapi/purchases")
def openapi_add_purchase(data: OpenApiPurchaseCreate, token: ApiTokenDB = Depends(verify_api_token), db: Session = Depends(get_db)):
    db_item = db.query(ItemDB).filter(ItemDB.id == data.item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="物品不存在")
    if data.quantity <= 0:
        raise HTTPException(status_code=400, detail="购买数量必须大于 0")
    if data.price < 0:
        raise HTTPException(status_code=400, detail="购买价格不能为负数")
    unit_price = round(data.price / data.quantity, 2)
    now = datetime.utcnow()
    db_purchase = PurchaseDB(item_id=data.item_id, quantity=data.quantity, price=data.price,
                             unit_price=unit_price, date=now)
    db_item.current_quantity += data.quantity
    db_item.last_purchase_date = now
    db.add(db_purchase)
    db.commit()
    return {"message": "购买记录已添加"}


@app.post("/openapi/usages")
def openapi_add_usage(data: OpenApiUsageCreate, token: ApiTokenDB = Depends(verify_api_token), db: Session = Depends(get_db)):
    db_item = db.query(ItemDB).filter(ItemDB.id == data.item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="物品不存在")
    if data.quantity <= 0:
        raise HTTPException(status_code=400, detail="使用数量必须大于 0")
    if db_item.current_quantity < data.quantity:
        raise HTTPException(status_code=400, detail="库存不足")
    now = datetime.utcnow()
    db_usage = UsageDB(item_id=data.item_id, quantity=data.quantity, date=now)
    db_item.current_quantity -= data.quantity
    db_item.last_usage_date = now
    db.add(db_usage)
    db.commit()
    check_low_inventory(db, db_item)
    return {"message": "使用记录已添加"}


# ===================== Static Files =====================
app.mount("/", StaticFiles(directory="app/static", html=True), name="static")
