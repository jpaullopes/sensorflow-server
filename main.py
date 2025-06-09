# main.py
from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, status, Depends, HTTPException, Request, Header, Query # Added Query
from pydantic import BaseModel
from typing import List, Optional, Dict
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os
from dotenv import load_dotenv

# SQLAlchemy
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Date, Time, inspect as sqlalchemy_inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import OperationalError, ArgumentError # Import both errors

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
DATABASE_URL = os.getenv("DATABASE_URL")

# --- Global Variables for Database (will be initialized on startup) ---
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


# --- Dependency to Verify API Key ---
async def verify_api_key(api_key: str = Header(None, alias="X-API-Key")):
    if not EXPECTED_API_KEY:
        print(f"{LogColors.FAIL}Server Error: Expected API key not configured.{LogColors.ENDC}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Server configuration error.")
    if not api_key or api_key != EXPECTED_API_KEY:
        print(f"{LogColors.WARNING}Attempt to access with invalid API Key.{LogColors.ENDC}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API Key.")
    return api_key

# --- WebSocket Connection Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"{LogColors.OKGREEN}New WebSocket client: {websocket.client.host}. Total: {len(self.active_connections)}{LogColors.ENDC}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        print(f"{LogColors.WARNING}WebSocket client disconnected. Total: {len(self.active_connections)}{LogColors.ENDC}")

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
        if db and app_state.db_is_connected:
            try:
                db.close()
            except OperationalError:
                pass


# --- Router for Endpoints ---
router = APIRouter()
app = FastAPI(title="Resilient Temperature Sensor API")

# --- Jinja2Templates Configuration ---
templates = Jinja2Templates(directory="templates")

# --- Robust Startup Logic ---
@app.on_event("startup")
async def on_startup():
    global engine, SessionLocal
    print(f"{LogColors.HEADER}Application starting...{LogColors.ENDC}")
    
    if not DATABASE_URL:
        app_state.db_is_connected = False
        print(f"{LogColors.WARNING}WARNING: DATABASE_URL not defined. The application will continue without saving data.{LogColors.ENDC}")
        return

    try:
        print("Configuring the database engine...")
        engine = create_engine(DATABASE_URL, connect_args={"connect_timeout": 5})
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        print("Attempting to connect to the database...")
        with engine.connect() as connection:
            print(f"{LogColors.OKGREEN}Database connection established successfully.{LogColors.ENDC}")
            
            inspector = sqlalchemy_inspect(engine)
            if not inspector.has_table(DataDB.__tablename__):
                print(f"Table '{DataDB.__tablename__}' not found. Attempting to create...")
                Base.metadata.create_all(bind=engine)
                print(f"{LogColors.OKCYAN}Table '{DataDB.__tablename__}' created successfully.{LogColors.ENDC}")
            else:
                print(f"{LogColors.OKCYAN}Table '{DataDB.__tablename__}' already exists. No action needed.{LogColors.ENDC}")

        app_state.db_is_connected = True

    except (OperationalError, ArgumentError) as e:
        app_state.db_is_connected = False
        print(f"{LogColors.FAIL}STARTUP ERROR: Could not configure or connect to the database.{LogColors.ENDC}")
        print(f"{LogColors.WARNING}WARNING: The application will continue to receive data, but NOTHING will be saved.{LogColors.ENDC}")
        if isinstance(e, ArgumentError):
            print(f"{LogColors.FAIL}Error detail: The provided database URL is invalid.{LogColors.ENDC}")
        else:
            print(f"{LogColors.FAIL}Error detail: Connection to the server failed.{LogColors.ENDC}")
            
    except Exception as e:
        app_state.db_is_connected = False
        print(f"{LogColors.FAIL}An unexpected error occurred during startup: {e}{LogColors.ENDC}")


# --- NEW ENDPOINT: Return HTML at root ---
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# --- HTTP Endpoint to receive data ---
@router.post(
    "/api/temperature_reading", 
    response_model=TemperatureDataResponse, 
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_api_key)]
)
async def submit_temperature_reading_http(
    payload: TemperatureReadingPayload, 
    request: Request,
    db: Optional[Session] = Depends(get_db) 
):
    client_ip = request.client.host if request.client else "unknown_ip"
    sensor_id = payload.sensor_id

    print(f"{LogColors.OKBLUE}HTTP: AUTHENTICATED request from {client_ip} (sensor: {sensor_id}){LogColors.ENDC}")

    utc_now = datetime.now(pytz.utc)
    brasilia_tz = pytz.timezone('America/Sao_Paulo')
    brasilia_now = utc_now.astimezone(brasilia_tz)
    date_to_store = brasilia_now.date()
    time_to_store = brasilia_now.time().replace(microsecond=0)

    print(f"{LogColors.OKBLUE}HTTP: Temperature received from {sensor_id}: {payload.temperature}°C{LogColors.ENDC}")
    
    db_data_entry = None

    if app_state.db_is_connected and db:
        try:
            db_data_entry = DataDB(
                temperature=payload.temperature, date_recorded=date_to_store,
                time_recorded=time_to_store, sensor_id=sensor_id, client_ip=client_ip
            )
            db.add(db_data_entry)
            db.commit()
            db.refresh(db_data_entry)
            print(f"{LogColors.OKGREEN}HTTP: Data from {sensor_id} saved to database. ID: {db_data_entry.id}{LogColors.ENDC}")

        except Exception as e:
            if db: db.rollback()
            # CHANGE: We update the global state here so that
            # all future requests (including WebSockets)
            # know that the database is offline.
            app_state.db_is_connected = False 
            print(f"{LogColors.FAIL}REAL-TIME ERROR: Database connection lost. Data not saved.{LogColors.ENDC}")
            print(f"{LogColors.WARNING}Error detail: {e}{LogColors.ENDC}")
            db_data_entry = None 
            
    else:
        print(f"{LogColors.WARNING}WARNING: Database unavailable. Data from {sensor_id} will not be saved.{LogColors.ENDC}")

    data_to_broadcast = TemperatureDataResponse(
        id=db_data_entry.id if db_data_entry else None,
        temperature=payload.temperature, date_recorded=date_to_store,
        time_recorded=time_to_store, sensor_id=sensor_id, client_ip=client_ip
    )

    await manager.broadcast_json(data_to_broadcast.model_dump(mode='json'))
    print(f"{LogColors.OKCYAN}HTTP: Data from {sensor_id} broadcast to {len(manager.active_connections)} WebSocket clients.{LogColors.ENDC}")
        
    return data_to_broadcast

# --- WebSocket Endpoint for clients to listen ---
@router.websocket("/ws/sensor_updates")
async def websocket_sensor_updates_endpoint(
    websocket: WebSocket,
    api_key: str = Query(..., alias="api-key"), # Added Query parameter for API Key in WS
    db: Optional[Session] = Depends(get_db)
):
    # First, verify the API key
    if not EXPECTED_API_KEY:
        print(f"{LogColors.FAIL}Server Error: Expected API key not configured for WebSocket.{LogColors.ENDC}")
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Server configuration error.")
        return

    if not api_key or api_key != EXPECTED_API_KEY:
        print(f"{LogColors.WARNING}Attempt to access WebSocket with invalid API Key: {api_key}{LogColors.ENDC}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid or missing API Key.")
        return

    # If the key is valid, proceed with the connection
    await manager.connect(websocket)
    print(f"{LogColors.OKGREEN}New AUTHENTICATED WebSocket client: {websocket.client.host}. Total: {len(manager.active_connections)}{LogColors.ENDC}")

    if app_state.db_is_connected and db:
        try:
            last_data_entry = db.query(DataDB).order_by(DataDB.id.desc()).first()
            if last_data_entry:
                await websocket.send_json(TemperatureDataResponse.from_orm(last_data_entry).model_dump(mode='json'))
        except Exception as e:
            # CHANGE: If the lookup fails, we also update the state.
            app_state.db_is_connected = False
            print(f"{LogColors.WARNING}WS: Error fetching last data, database now marked as offline: {e}{LogColors.ENDC}")

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"{LogColors.FAIL}Unexpected error in WebSocket: {e}{LogColors.ENDC}")
    finally:
        manager.disconnect(websocket)

app.include_router(router)