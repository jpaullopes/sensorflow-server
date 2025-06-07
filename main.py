# main.py
from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, status, Depends, HTTPException, Request, Header
from pydantic import BaseModel
from typing import List, Optional, Dict
import os
from dotenv import load_dotenv

# SQLAlchemy
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Date, Time, inspect as sqlalchemy_inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import OperationalError, ArgumentError # Importar ambos os erros

# Timestamp e Fuso Horário
from datetime import datetime, date as date_type, time as time_type
import pytz

# Carregar variáveis de ambiente do ficheiro .env
load_dotenv() 

# --- Cores para Logs (Opcional, para melhor visualização no terminal) ---
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

# --- Estado Global da Aplicação ---
class AppState:
    """Uma classe simples para guardar o estado da conexão com o banco de dados."""
    def __init__(self):
        self.db_is_connected: bool = False

app_state = AppState()

# --- Configurações Iniciais ---
EXPECTED_API_KEY = os.getenv("API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

# --- Variáveis Globais para o Banco de Dados (serão inicializadas no startup) ---
engine = None
SessionLocal = None
Base = declarative_base()

# --- Modelos SQLAlchemy (Tabelas da Base de Dados) ---
class DataDB(Base):
    __tablename__ = "data"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    temperature = Column(Float, nullable=False)
    date_recorded = Column(Date, nullable=False, index=True)      
    time_recorded = Column(Time, nullable=False, index=True)
    sensor_id = Column(String, nullable=False, index=True)
    client_ip = Column(String, nullable=True)


# --- Dependência para Verificar a Chave de API ---
async def verify_api_key(api_key: str = Header(None, alias="X-API-Key")):
    if not EXPECTED_API_KEY:
        print(f"{LogColors.FAIL}Erro de servidor: Chave de API esperada não configurada.{LogColors.ENDC}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Server configuration error.")
    if not api_key or api_key != EXPECTED_API_KEY:
        print(f"{LogColors.WARNING}Tentativa de acesso com API Key inválida: {api_key}{LogColors.ENDC}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API Key.")
    return api_key

# --- Gestor de Conexões WebSocket ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"{LogColors.OKGREEN}Novo cliente WebSocket: {websocket.client.host}. Total: {len(self.active_connections)}{LogColors.ENDC}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        print(f"{LogColors.WARNING}Cliente WebSocket desconectado. Total: {len(self.active_connections)}{LogColors.ENDC}")

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

# --- Modelos Pydantic ---
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

# --- Dependência para obter a Sessão da Base de Dados ---
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


# --- Router para Endpoints ---
router = APIRouter()
app = FastAPI(title="API de Sensor de Temperatura Resiliente")

# --- Lógica de Inicialização Robusta ---
@app.on_event("startup")
async def on_startup():
    global engine, SessionLocal
    print(f"{LogColors.HEADER}Aplicação a iniciar...{LogColors.ENDC}")
    
    if not DATABASE_URL:
        app_state.db_is_connected = False
        print(f"{LogColors.WARNING}AVISO: DATABASE_URL não definida. A aplicação continuará sem salvar dados.{LogColors.ENDC}")
        return

    try:
        print("A configurar o motor do banco de dados...")
        engine = create_engine(DATABASE_URL, connect_args={"connect_timeout": 5})
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        print("A tentar conectar ao banco de dados...")
        with engine.connect() as connection:
            print(f"{LogColors.OKGREEN}Conexão com o banco de dados estabelecida com sucesso.{LogColors.ENDC}")
            
            inspector = sqlalchemy_inspect(engine)
            if not inspector.has_table(DataDB.__tablename__):
                print(f"Tabela '{DataDB.__tablename__}' não encontrada. A tentar criar...")
                Base.metadata.create_all(bind=engine)
                print(f"{LogColors.OKCYAN}Tabela '{DataDB.__tablename__}' criada com sucesso.{LogColors.ENDC}")
            else:
                print(f"{LogColors.OKCYAN}Tabela '{DataDB.__tablename__}' já existe. Nenhuma ação necessária.{LogColors.ENDC}")

        app_state.db_is_connected = True

    except (OperationalError, ArgumentError) as e:
        app_state.db_is_connected = False
        print(f"{LogColors.FAIL}ERRO DE STARTUP: Não foi possível configurar ou conectar ao banco de dados.{LogColors.ENDC}")
        print(f"{LogColors.WARNING}AVISO: A aplicação continuará a receber dados, mas NADA será salvo.{LogColors.ENDC}")
        if isinstance(e, ArgumentError):
            print(f"{LogColors.FAIL}Detalhe do erro: A URL do banco de dados fornecida é inválida.{LogColors.ENDC}")
        else:
            print(f"{LogColors.FAIL}Detalhe do erro: A conexão com o servidor falhou.{LogColors.ENDC}")
            
    except Exception as e:
        app_state.db_is_connected = False
        print(f"{LogColors.FAIL}Um erro inesperado ocorreu durante a inicialização: {e}{LogColors.ENDC}")


# --- Endpoint HTTP para receber dados ---
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

    print(f"{LogColors.OKBLUE}HTTP: Requisição AUTENTICADA de {client_ip} (sensor: {sensor_id}){LogColors.ENDC}")

    utc_now = datetime.now(pytz.utc)
    brasilia_tz = pytz.timezone('America/Sao_Paulo')
    brasilia_now = utc_now.astimezone(brasilia_tz)
    date_to_store = brasilia_now.date()
    time_to_store = brasilia_now.time().replace(microsecond=0)

    print(f"{LogColors.OKBLUE}HTTP: Temperatura recebida de {sensor_id}: {payload.temperature}°C{LogColors.ENDC}")
    
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
            print(f"{LogColors.OKGREEN}HTTP: Dados de {sensor_id} guardados no banco. ID: {db_data_entry.id}{LogColors.ENDC}")

        except Exception as e:
            if db: db.rollback()
            # MUDANÇA: Atualizamos o estado global aqui para que
            # todas as futuras requisições (incluindo WebSockets)
            # saibam que o banco está offline.
            app_state.db_is_connected = False 
            print(f"{LogColors.FAIL}ERRO EM TEMPO REAL: Conexão com o banco perdida. Dados não salvos.{LogColors.ENDC}")
            print(f"{LogColors.WARNING}Detalhe do erro: {e}{LogColors.ENDC}")
            db_data_entry = None 
            
    else:
        print(f"{LogColors.WARNING}AVISO: Banco de dados indisponível. Dados de {sensor_id} não serão salvos.{LogColors.ENDC}")

    data_to_broadcast = TemperatureDataResponse(
        id=db_data_entry.id if db_data_entry else None,
        temperature=payload.temperature, date_recorded=date_to_store,
        time_recorded=time_to_store, sensor_id=sensor_id, client_ip=client_ip
    )

    await manager.broadcast_json(data_to_broadcast.model_dump(mode='json'))
    print(f"{LogColors.OKCYAN}HTTP: Dados de {sensor_id} transmitidos para {len(manager.active_connections)} clientes WebSocket.{LogColors.ENDC}")
        
    return data_to_broadcast

# --- Endpoint WebSocket para clientes escutarem ---
@router.websocket("/ws/sensor_updates")
async def websocket_sensor_updates_endpoint(websocket: WebSocket, db: Optional[Session] = Depends(get_db)):
    await manager.connect(websocket)
    
    if app_state.db_is_connected and db:
        try:
            last_data_entry = db.query(DataDB).order_by(DataDB.id.desc()).first()
            if last_data_entry:
                await websocket.send_json(TemperatureDataResponse.from_orm(last_data_entry).model_dump(mode='json'))
        except Exception as e:
            # MUDANÇA: Se a busca falhar, também atualizamos o estado.
            app_state.db_is_connected = False
            print(f"{LogColors.WARNING}WS: Erro ao buscar último dado, banco agora marcado como offline: {e}{LogColors.ENDC}")

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)

app.include_router(router)
