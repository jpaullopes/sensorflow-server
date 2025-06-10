# main.py
from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, status, Depends, HTTPException, Request, Header, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
import os
from dotenv import load_dotenv

# SQLAlchemy
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Date, Time, inspect as sqlalchemy_inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import OperationalError, ArgumentError

# Timestamp and Timezone
from datetime import datetime, date as date_type, time as time_type
import pytz

# Load environment variables from .env file
load_dotenv() 

# --- Log Colors (Optional, for better terminal visualization) ---
class LogColors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

# --- Global Application State ---
class AppState:
    """A simple class to hold the database connection state."""
    def __init__(self):
        self.db_is_connected: bool = False

app_state = AppState()

# --- Initial Configurations ---
EXPECTED_API_KEY = os.getenv("API_KEY")
EXPECTED_API_KEY_WS = os.getenv("API_KEY_WS") 
DATABASE_URL = os.getenv("DATABASE_URL")
MAX_WS_CONNECTIONS_PER_KEY_STR = os.getenv("MAX_WS_CONNECTIONS_PER_KEY")
MAX_WS_CONNECTIONS_PER_KEY: int = 0

try:
    if MAX_WS_CONNECTIONS_PER_KEY_STR:
        MAX_WS_CONNECTIONS_PER_KEY = int(MAX_WS_CONNECTIONS_PER_KEY_STR)
        if MAX_WS_CONNECTIONS_PER_KEY < 0:
            MAX_WS_CONNECTIONS_PER_KEY = 0
except ValueError:
    print(f"{LogColors.WARNING}WARNING: MAX_WS_CONNECTIONS_PER_KEY is not a valid number. Setting to unlimited.{LogColors.ENDC}")

# --- Global Variables for Database ---
engine = None
SessionLocal = None
Base = declarative_base()

# --- SQLAlchemy Models (Database Tables) ---
class DataDB(Base):
    __tablename__ = "data"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    temperature = Column(Float, nullable=False)
    date_recorded = Column(Date, nullable=False, index=True)      
    time_recorded = Column(Time, nullable=False, index=True)
    sensor_id = Column(String, nullable=False, index=True)
    client_ip = Column(String, nullable=True)

# --- Dependency to Verify API Key (for HTTP endpoint) ---
async def verify_api_key(api_key: str = Header(None, alias="X-API-Key")):
    if not EXPECTED_API_KEY:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Server configuration error.")
    if not api_key or api_key != EXPECTED_API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API Key.")
    return api_key

# --- WebSocket Connection Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.connections_per_key: Dict[str, int] = {} 
        self.websocket_to_key_map: Dict[WebSocket, str] = {} 

    async def connect(self, websocket: WebSocket, api_key: str) -> bool:
        if MAX_WS_CONNECTIONS_PER_KEY > 0 and self.connections_per_key.get(api_key, 0) >= MAX_WS_CONNECTIONS_PER_KEY:
            return False 
        await websocket.accept()
        self.active_connections.append(websocket)
        self.connections_per_key[api_key] = self.connections_per_key.get(api_key, 0) + 1 
        self.websocket_to_key_map[websocket] = api_key 
        print(f"{LogColors.OKGREEN}New WebSocket client: {websocket.client.host} (Key: {api_key}). Total connections for this key: {self.connections_per_key[api_key]}. Global total: {len(self.active_connections)}{LogColors.ENDC}")
        return True

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            api_key = self.websocket_to_key_map.pop(websocket, None) 
            if api_key:
                self.connections_per_key[api_key] = self.connections_per_key.get(api_key, 1) - 1 
                if self.connections_per_key[api_key] <= 0:
                    del self.connections_per_key[api_key] 
                print(f"{LogColors.WARNING}WebSocket client disconnected. Total connections for key '{api_key}': {self.connections_per_key.get(api_key, 0)}. Global total: {len(self.active_connections)}{LogColors.ENDC}")
            else:
                print(f"{LogColors.WARNING}WebSocket client disconnected (key not mapped). Global total: {len(self.active_connections)}{LogColors.ENDC}")

    async def broadcast_json(self, data: dict):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(data)
            except Exception:
                disconnected.append(connection)
        for ws_to_remove in disconnected:
            self.disconnect(ws_to_remove)

manager = ConnectionManager()

# --- Pydantic Models ---
class TemperatureReadingPayload(BaseModel):
    temperature: float
    sensor_id: str

class TemperatureDataResponse(BaseModel):
    id: Optional[int] = None
    temperature: float
    date_recorded: date_type
    time_recorded: time_type
    sensor_id: str
    client_ip: Optional[str] = None
    class Config:
        from_attributes = True

# --- Dependency to get Database Session ---
def get_db():
    if not app_state.db_is_connected or not SessionLocal:
        yield None
        return
    db = SessionLocal()
    try:
        yield db
    finally:
        if db:
            db.close()

# --- Router for Endpoints ---
router = APIRouter()
app = FastAPI(title="Resilient Temperature Sensor API")
templates = Jinja2Templates(directory="templates")

# --- Robust Startup Logic ---
@app.on_event("startup")
async def on_startup():
    global engine, SessionLocal
    print(f"{LogColors.HEADER}Application starting...{LogColors.ENDC}")
    if not DATABASE_URL:
        print(f"{LogColors.WARNING}WARNING: DATABASE_URL not defined...{LogColors.ENDC}")
    if DATABASE_URL:
        try:
            engine = create_engine(DATABASE_URL, connect_args={"connect_timeout": 5})
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            with engine.connect() as connection:
                print(f"{LogColors.OKGREEN}Database connection established successfully.{LogColors.ENDC}")
                inspector = sqlalchemy_inspect(engine)
                if not inspector.has_table(DataDB.__tablename__):
                    Base.metadata.create_all(bind=engine)
                    print(f"{LogColors.OKCYAN}Table '{DataDB.__tablename__}' created.{LogColors.ENDC}")
                app_state.db_is_connected = True
        except Exception as e:
            app_state.db_is_connected = False
            print(f"{LogColors.FAIL}STARTUP ERROR: Could not connect to the database: {e}{LogColors.ENDC}")

# --- HTML Endpoint ---
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# --- HTTP Endpoint to receive data ---
@router.post("/api/temperature_reading", response_model=TemperatureDataResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_api_key)])
async def submit_temperature_reading_http(payload: TemperatureReadingPayload, request: Request, db: Optional[Session] = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown_ip"
    utc_now = datetime.now(pytz.utc)
    brasilia_tz = pytz.timezone('America/Sao_Paulo')
    brasilia_now = utc_now.astimezone(brasilia_tz)
    date_to_store = brasilia_now.date()
    time_to_store = brasilia_now.time().replace(microsecond=0)
    db_data_entry = None

    if app_state.db_is_connected and db:
        try:
            db_data_entry = DataDB(temperature=payload.temperature, date_recorded=date_to_store, time_recorded=time_to_store, sensor_id=payload.sensor_id, client_ip=client_ip)
            db.add(db_data_entry)
            db.commit()
            db.refresh(db_data_entry)
        except Exception as e:
            if db: db.rollback()
            # <<< MUDANÇA 1: Se a conexão com o BD falhar, avise os clientes via WebSocket
            if app_state.db_is_connected:  # Apenas avise na primeira vez que falhar
                app_state.db_is_connected = False
                print(f"{LogColors.FAIL}REAL-TIME ERROR: Database connection lost. Broadcasting status...{LogColors.ENDC}")
                status_payload = {"type": "status_update", "payload": {"db_connected": False, "timestamp": utc_now.isoformat()}}
                await manager.broadcast_json(status_payload)
            db_data_entry = None
            
    # <<< MUDANÇA 2: Envelopa a mensagem do sensor com o tipo e payload
    data_for_response = TemperatureDataResponse(id=db_data_entry.id if db_data_entry else None, temperature=payload.temperature, date_recorded=date_to_store, time_recorded=time_to_store, sensor_id=payload.sensor_id, client_ip=client_ip)
    message_to_broadcast = {
        "type": "sensor_data",
        "payload": data_for_response.model_dump(mode='json')
    }
    await manager.broadcast_json(message_to_broadcast)
    print(f"{LogColors.OKCYAN}HTTP: Data broadcast to {len(manager.active_connections)} WebSocket clients.{LogColors.ENDC}")
    return data_for_response

# --- WebSocket Endpoint for clients to listen ---
@router.websocket("/ws/sensor_updates")
async def websocket_sensor_updates_endpoint(websocket: WebSocket, api_key: str = Query(..., alias="api-key"), db: Optional[Session] = Depends(get_db)):
    if not EXPECTED_API_KEY_WS or api_key != EXPECTED_API_KEY_WS:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid or missing API Key.")
        return
    
    connection_accepted = await manager.connect(websocket, api_key)
    if not connection_accepted:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Max connections reached.")
        return

    # <<< MUDANÇA 3: Envia um estado inicial completo para o novo cliente conectado
    last_data_payload = None
    if app_state.db_is_connected and db:
        try:
            last_data_entry = db.query(DataDB).order_by(DataDB.id.desc()).first()
            if last_data_entry:
                last_data_payload = TemperatureDataResponse.from_orm(last_data_entry).model_dump(mode='json')
        except Exception as e:
            print(f"{LogColors.WARNING}WS: Error fetching last data entry: {e}{LogColors.ENDC}")

    initial_state_message = {
        "type": "initial_state",
        "payload": {
            "db_connected": app_state.db_is_connected,
            "last_sensor_data": last_data_payload
        }
    }
    await websocket.send_json(initial_state_message)
    # Fim da Mudança 3

    try:
        while True:
            await websocket.receive_text() # Apenas mantém a conexão viva, não espera mensagens do cliente
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)

app.include_router(router)