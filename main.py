from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, status, Depends, HTTPException, Request, Header # Adicionado Header
from pydantic import BaseModel
from typing import List, Optional, Dict
import os
from dotenv import load_dotenv

# SQLAlchemy
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Date, Time
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.sql import func

# Timestamp e Fuso Horário
from datetime import datetime, date as date_type, time as time_type
import pytz

load_dotenv() 

# --- Cores para Logs ---
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

EXPECTED_API_KEY = os.getenv("API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

if not EXPECTED_API_KEY:
    print(f"{LogColors.WARNING}WARNING: A variável de ambiente 'API_KEY' não está definida. A autenticação por API Key para o endpoint HTTP não funcionará corretamente.{LogColors.ENDC}")
    # Em produção, você pode querer levantar um erro aqui:
    # raise ValueError("API_KEY não configurada no ambiente.")

# --- Dependência para Verificar a Chave de API ---
async def verify_api_key(api_key: str = Header(None, alias="X-API-Key")):
    """Dependência para verificar a chave de API no cabeçalho X-API-Key."""
    if not EXPECTED_API_KEY: # Se a chave esperada não foi carregada do .env
        print(f"{LogColors.FAIL}Erro de servidor: Chave de API esperada não configurada no servidor.{LogColors.ENDC}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server configuration error regarding API Key."
        )
    if not api_key:
        print(f"{LogColors.WARNING}Tentativa de acesso sem API Key header 'X-API-Key'.{LogColors.ENDC}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key header 'X-API-Key' missing."
        )
    if api_key != EXPECTED_API_KEY:
        print(f"{LogColors.WARNING}Tentativa de acesso com API Key inválida: {api_key}{LogColors.ENDC}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or incorrect API Key."
        )
    # Se a chave for válida, pode retornar algo ou simplesmente não levantar exceção.
    # Retornar a chave pode ser útil se você quiser usá-la ou logá-la (com cuidado).
    return api_key


# --- Gestor de Conexões WebSocket ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        count = len(self.active_connections)
        print(f"{LogColors.OKGREEN}Novo cliente WebSocket conectado: {websocket.client.host}:{websocket.client.port}. Total de conexões: {count}{LogColors.ENDC}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        count = len(self.active_connections)
        print(f"{LogColors.WARNING}Cliente WebSocket desconectado: {websocket.client.host}:{websocket.client.port}. Total de conexões: {count}{LogColors.ENDC}")

    async def broadcast_json(self, data: dict):
        disconnected_websockets = []
        for connection in self.active_connections:
            try:
                await connection.send_json(data)
            except Exception as e:
                print(f"{LogColors.FAIL}Erro ao transmitir para {connection.client.host}: {e}. Marcando para desconexão.{LogColors.ENDC}")
                disconnected_websockets.append(connection)
        
        for ws_to_remove in disconnected_websockets:
            self.disconnect(ws_to_remove)

manager = ConnectionManager()

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
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

# --- Criação das Tabelas na Base de Dados ---
def create_db_and_tables():
    try:
        Base.metadata.create_all(bind=engine)
        print(f"{LogColors.OKCYAN}Tabelas (incluindo 'data') verificadas/criadas com sucesso no PostgreSQL.{LogColors.ENDC}")
    except Exception as e:
        print(f"{LogColors.FAIL}Erro ao criar tabelas no PostgreSQL: {e}{LogColors.ENDC}")

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
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Router para Endpoints ---
router = APIRouter()
app = FastAPI(title="API de Sensor de Temperatura: HTTP com API Key, WebSocket para Clientes")

@app.on_event("startup")
async def on_startup():
    print(f"{LogColors.HEADER}Aplicação a iniciar...{LogColors.ENDC}")
    create_db_and_tables()

# --- Endpoint HTTP para a plaquinha enviar dados ---
@router.post(
    "/api/temperature_reading", 
    response_model=TemperatureDataResponse, 
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_api_key)] # ADICIONADA A DEPENDÊNCIA DE VERIFICAÇÃO DA API KEY
)
async def submit_temperature_reading_http(
    payload: TemperatureReadingPayload, 
    request: Request,
    db: Session = Depends(get_db)
    # api_key_verified: str = Depends(verify_api_key) # Alternativa: se quiser usar o valor retornado pela dependência
):
    client_ip = request.client.host if request.client else "unknown_ip"
    sensor_id = payload.sensor_id

    # print(f"API Key Verificada: {api_key_verified}") # Se usar a alternativa acima

    print(f"{LogColors.OKBLUE}HTTP: Requisição AUTENTICADA recebida de IP: {client_ip} com sensor_id: {sensor_id}{LogColors.ENDC}")

    try:
        utc_now = datetime.now(pytz.utc)
        brasilia_tz = pytz.timezone('America/Sao_Paulo')
        brasilia_now = utc_now.astimezone(brasilia_tz)

        date_to_store = brasilia_now.date()
        time_to_store = brasilia_now.time().replace(microsecond=0)

        print(f"{LogColors.OKBLUE}HTTP: Temperatura recebida de {sensor_id}: {payload.temperature}°C às {date_to_store} {time_to_store.strftime('%H:%M:%S')} (Horário de Brasília){LogColors.ENDC}")
        
        db_data_entry = DataDB(
            temperature=payload.temperature,
            date_recorded=date_to_store,
            time_recorded=time_to_store,
            sensor_id=sensor_id,
            client_ip=client_ip
        )
        db.add(db_data_entry)
        db.commit()
        db.refresh(db_data_entry)
        
        print(f"{LogColors.OKGREEN}HTTP: Dados de {sensor_id} (IP: {client_ip}) guardados na base de dados. ID: {db_data_entry.id}{LogColors.ENDC}")

        data_to_broadcast = TemperatureDataResponse.from_orm(db_data_entry)
        
        await manager.broadcast_json(data_to_broadcast.model_dump(mode='json'))
        print(f"{LogColors.OKCYAN}HTTP: Dados de {sensor_id} transmitidos para {len(manager.active_connections)} clientes WebSocket.{LogColors.ENDC}")
        
        return data_to_broadcast

    except Exception as e:
        db.rollback()
        print(f"{LogColors.FAIL}HTTP: Erro ao processar leitura de temperatura de {sensor_id} (IP: {client_ip}): {e}{LogColors.ENDC}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno ao processar os dados do sensor: {str(e)}"
        )

# --- Endpoint WebSocket para clientes escutarem atualizações ---
@router.websocket("/ws/sensor_updates")
async def websocket_sensor_updates_endpoint(websocket: WebSocket, db: Session = Depends(get_db)):
    await manager.connect(websocket)
    
    try:
        last_data_entry = db.query(DataDB).order_by(DataDB.date_recorded.desc(), DataDB.time_recorded.desc()).first()
        if last_data_entry:
            await websocket.send_json(TemperatureDataResponse.from_orm(last_data_entry).model_dump(mode='json'))
    except Exception as e:
        print(f"{LogColors.WARNING}WS: Erro ao enviar último dado para {websocket.client.host}: {e}{LogColors.ENDC}")

    try:
        while True:
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"{LogColors.FAIL}WS: Exceção inesperada com {websocket.client.host}: {e}{LogColors.ENDC}")
    finally:
        manager.disconnect(websocket)

app.include_router(router)

# Para executar este exemplo:
# 1. Defina a variável de ambiente API_KEY. Ex: export API_KEY="sua_chave_super_secreta"
# 2. Certifique-se de que a sua DATABASE_URL está correta.
# 3. Instale as dependências: pip install fastapi uvicorn pydantic sqlalchemy psycopg2-binary pytz python-dotenv (para .env)
# 4. Guarde como main.py.
# 5. Execute com uvicorn: uvicorn main:app --reload
#
# Para testar a rota HTTP (plaquinha):
# POST para http://localhost:8000/api/temperature_reading
# Headers: X-API-Key: sua_chave_super_secreta
# Corpo JSON: {"temperature": 23.5, "sensor_id": "sensor_cozinha"}