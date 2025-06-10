# main.py
from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, status, Depends, HTTPException, Request, Header, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
import os
from dotenv import load_dotenv
import logging
import colorlog # Importe colorlog

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

# --- Configure Logging with Colors ---
# Crie um logger personalizado
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO) # Defina o nível mínimo de log

# Crie um handler para o console
console_handler = logging.StreamHandler()

# Defina o formatador colorido usando colorlog
# Os códigos de cor são definidos para cada nível de log
formatter = colorlog.ColoredFormatter(
    "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    log_colors={
        'DEBUG':    'cyan',
        'INFO':     'green',
        'WARNING':  'yellow',
        'ERROR':    'red',
        'CRITICAL': 'bold_red',
    },
    secondary_log_colors={},
    style='%'
)

# Adicione o formatador ao handler do console
console_handler.setFormatter(formatter)

# Adicione o handler ao logger
logger.addHandler(console_handler)

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

# NOVO: Variável de ambiente para o número máximo de conexões WebSocket por chave
# O valor padrão é 0, significando conexões ilimitadas se não for definido ou for inválido.
MAX_WS_CONNECTIONS_PER_KEY_STR = os.getenv("MAX_WS_CONNECTIONS_PER_KEY")
MAX_WS_CONNECTIONS_PER_KEY: int = 0 # Default to 0 (unlimited)
try:
    if MAX_WS_CONNECTIONS_PER_KEY_STR:
        MAX_WS_CONNECTIONS_PER_KEY = int(MAX_WS_CONNECTIONS_PER_KEY_STR)
        if MAX_WS_CONNECTIONS_PER_KEY < 0: # Ensures it's not negative
            MAX_WS_CONNECTIONS_PER_KEY = 0
except ValueError:
    logger.warning("MAX_WS_CONNECTIONS_PER_KEY is not a valid number. Setting to unlimited.")


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


# --- Dependency to Verify API Key (for HTTP endpoint) ---
async def verify_api_key(api_key: str = Header(None, alias="X-API-Key")):
    if not EXPECTED_API_KEY:
        logger.error("Server Error: Expected API key (HTTP) not configured.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Server configuration error.")
    if not api_key or api_key != EXPECTED_API_KEY:
        logger.warning("Attempt to access with invalid API Key (HTTP).")
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
            logger.warning(f"WebSocket connection rejected for API Key '{api_key}': max connections ({MAX_WS_CONNECTIONS_PER_KEY}) reached. Client: {websocket.client.host}")
            return False

        await websocket.accept()
        self.active_connections.append(websocket)
        self.connections_per_key[api_key] = self.connections_per_key.get(api_key, 0) + 1
        self.websocket_to_key_map[websocket] = api_key
        logger.info(f"New WebSocket client: {websocket.client.host} (Key: {api_key}). Total connections for this key: {self.connections_per_key[api_key]}. Global total: {len(self.active_connections)}")
        return True

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            api_key = self.websocket_to_key_map.pop(websocket, None)
            if api_key:
                self.connections_per_key[api_key] = self.connections_per_key.get(api_key, 1) - 1
                if self.connections_per_key[api_key] <= 0:
                    del self.connections_per_key[api_key]
                logger.warning(f"WebSocket client disconnected. Total connections for key '{api_key}': {self.connections_per_key.get(api_key, 0)}. Global total: {len(self.active_connections)}")
            else:
                logger.warning(f"WebSocket client disconnected (key not mapped). Global total: {len(self.active_connections)}")
        else:
            logger.warning("Attempted to disconnect a non-active WebSocket.")

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
    logger.info("Application starting...")

    if not DATABASE_URL:
        app_state.db_is_connected = False
        logger.warning("DATABASE_URL not defined. The application will continue without saving data.")

    if not EXPECTED_API_KEY:
        logger.warning("API_KEY (for HTTP endpoints) not defined. HTTP API endpoints might be unprotected or fail.")

    if not EXPECTED_API_KEY_WS:
        logger.warning("API_KEY_WS (for WebSocket endpoint) not defined. WebSocket endpoint might be unprotected or fail.")

    if MAX_WS_CONNECTIONS_PER_KEY == 0:
        logger.info("MAX_WS_CONNECTIONS_PER_KEY not defined or set to 0. WebSocket connections will be UNLIMITED per API Key.")
    else:
        logger.info(f"WebSocket connections limited to {MAX_WS_CONNECTIONS_PER_KEY} per API Key.")


    if DATABASE_URL:
        try:
            logger.info("Configuring the database engine...")
            engine = create_engine(DATABASE_URL, connect_args={"connect_timeout": 5})
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

            logger.info("Attempting to connect to the database...")
            with engine.connect() as connection:
                logger.info("Database connection established successfully.")

                inspector = sqlalchemy_inspect(engine)
                if not inspector.has_table(DataDB.__tablename__):
                    logger.info(f"Table '{DataDB.__tablename__}' not found. Attempting to create...")
                    Base.metadata.create_all(bind=engine)
                    logger.info(f"Table '{DataDB.__tablename__}' created successfully.")
                else:
                    logger.info(f"Table '{DataDB.__tablename__}' already exists. No action needed.")

            app_state.db_is_connected = True

        except (OperationalError, ArgumentError) as e:
            app_state.db_is_connected = False
            logger.error("STARTUP ERROR: Could not configure or connect to the database.")
            logger.warning("The application will continue to receive data, but NOTHING will be saved.")
            if isinstance(e, ArgumentError):
                logger.error("Error detail: The provided database URL is invalid.")
            else:
                logger.error("Error detail: Connection to the server failed.")

        except Exception as e:
            app_state.db_is_connected = False
            logger.exception(f"An unexpected error occurred during startup: {e}")
    else:
        pass


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

    logger.info(f"HTTP: AUTHENTICATED request from {client_ip} (sensor: {sensor_id})")

    utc_now = datetime.now(pytz.utc)
    brasilia_tz = pytz.timezone('America/Sao_Paulo')
    brasilia_now = utc_now.astimezone(brasilia_tz)
    date_to_store = brasilia_now.date()
    time_to_store = brasilia_now.time().replace(microsecond=0)

    logger.info(f"HTTP: Temperatura recebida de {sensor_id}: {payload.temperature}°C")

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
            logger.info(f"HTTP: Data from {sensor_id} saved to database. ID: {db_data_entry.id}")

        except Exception as e:
            if db: db.rollback()
            app_state.db_is_connected = False
            logger.error("REAL-TIME ERROR: Database connection lost. Data not saved.")
            logger.error(f"Error detail: {e}")
            db_data_entry = None

    else:
        logger.warning(f"WARNING: Database unavailable. Data from {sensor_id} will not be saved.")

    data_to_broadcast = TemperatureDataResponse(
        id=db_data_entry.id if db_data_entry else None,
        temperature=payload.temperature, date_recorded=date_to_store,
        time_recorded=time_to_store, sensor_id=sensor_id, client_ip=client_ip
    )

    await manager.broadcast_json(data_to_broadcast.model_dump(mode='json'))
    logger.info(f"HTTP: Data from {sensor_id} broadcast to {len(manager.active_connections)} WebSocket clients.")

    return data_to_broadcast

# --- WebSocket Endpoint for clients to listen ---
@router.websocket("/ws/sensor_updates")
async def websocket_sensor_updates_endpoint(
    websocket: WebSocket,
    api_key: str = Query(..., alias="api-key"),
    db: Optional[Session] = Depends(get_db)
):
    if not EXPECTED_API_KEY_WS:
        logger.error("Server Error: Expected API key (WebSocket) not configured.")
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Server configuration error.")
        return

    if not api_key or api_key != EXPECTED_API_KEY_WS:
        logger.warning(f"Attempt to access WebSocket with invalid API Key: {api_key}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid or missing API Key.")
        return

    if MAX_WS_CONNECTIONS_PER_KEY > 0 and manager.connections_per_key.get(api_key, 0) >= MAX_WS_CONNECTIONS_PER_KEY:
        logger.warning(f"WebSocket connection rejected for API Key '{api_key}': max connections ({MAX_WS_CONNECTIONS_PER_KEY}) reached. Client: {websocket.client.host}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=f"Max connections ({MAX_WS_CONNECTIONS_PER_KEY}) for this API Key reached.")
        return

    connection_accepted = await manager.connect(websocket, api_key)

    if not connection_accepted:
        return

    if app_state.db_is_connected and db:
        try:
            last_data_entry = db.query(DataDB).order_by(DataDB.id.desc()).first()
            if last_data_entry:
                await websocket.send_json(TemperatureDataResponse.from_orm(last_data_entry).model_dump(mode='json'))
        except Exception as e:
            app_state.db_is_connected = False
            logger.warning(f"WS: Error fetching last data, database now marked as offline: {e}")

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected gracefully.")
        pass
    except Exception as e:
        logger.exception(f"Unexpected error in WebSocket: {e}")
    finally:
        manager.disconnect(websocket)

app.include_router(router)