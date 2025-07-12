# SensorFlow Server

![Linguagem](https://img.shields.io/badge/Linguagem-python-green.svg)
![Badge de Versão](https://img.shields.io/badge/version-2.0.0-blue)
![Licença](https://img.shields.io/badge/Licen%C3%A7a-MIT-yellow.svg)

Uma aplicação de backend desenvolvida em Python com FastAPI, projetada para coletar, armazenar e distribuir dados de sensores em tempo real. A arquitetura modular é otimizada para ser resiliente, escalável e de fácil manutenção.

## 🚀 Funcionalidades

- **API REST Segura**: Recebe dados de sensores (temperatura, umidade e pressão) através de endpoint HTTP POST protegido por API Key
- **WebSocket em Tempo Real**: Distribui instantaneamente os dados recebidos para todos os clientes conectados
- **Banco de Dados PostgreSQL**: Armazenamento persistente com criação automática de tabelas
- **Visualização com Grafana**: Dashboard integrado para monitoramento e análise dos dados
- **Autenticação Dupla**: API Keys separadas para HTTP e WebSocket
- **Limite de Conexões**: Controle configurável de conexões WebSocket por API Key
- **Logs Coloridos**: Sistema de logging avançado com cores para melhor debugging
- **Arquitetura Modular**: Código organizado em módulos específicos para facilitar manutenção
- **Docker Compose**: Stack completa com API + PostgreSQL + Grafana

## 🏗️ Arquitetura Modular

```
sensorflow-server/
├── main.py                    # 🚀 Ponto de entrada da aplicação
├── src/                       # 📁 Código fonte modular
│   ├── __init__.py           # 📦 Inicialização do pacote
│   ├── config.py             # ⚙️ Configurações e variáveis de ambiente
│   ├── logger_config.py      # 📝 Sistema de logs coloridos
│   ├── models.py             # 🏗️ Modelos SQLAlchemy e Pydantic
│   ├── database.py           # 💾 Configuração e conexão do banco
│   ├── auth.py               # 🔐 Autenticação e verificação de API Keys
│   ├── websocket_manager.py  # 🌐 Gerenciamento de conexões WebSocket
│   └── routes/               # �️ Endpoints organizados
│       ├── __init__.py       # 📦 Exportação dos roteadores
│       ├── api_routes.py     # 📡 Endpoints HTTP da API
│       └── websocket_routes.py # 🔌 Endpoints WebSocket
├── docker-compose.yml        # 🐳 Orquestração dos serviços
├── Dockerfile               # 🐳 Imagem da aplicação
├── requirements.txt         # 📋 Dependências Python
└── README.md               # 📖 Documentação

## 📋 Pré-requisitos

Antes de começar, garanta que você tenha as seguintes ferramentas instaladas:
- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

## ⚙️ Instalação e Execução

## 🛠️ Tecnologias Utilizadas

- **Backend**: Python, FastAPI
- **Banco de Dados**: PostgreSQL (via SQLAlchemy)
- **Visualização**: Grafana OSS
- **Comunicação em Tempo Real**: WebSockets
- **Contêineres**: Docker, Docker Compose
- **Logging**: ColorLog para logs coloridos

## 📋 Pré-requisitos

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

## ⚙️ Instalação e Execução

### 1. Clone o Repositório

```bash
git clone https://github.com/jpaullopes/sensorflow-server.git
cd sensorflow-server
```

### 2. Configure as Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto:

```dotenv
# API Keys para proteger os endpoints
API_KEY=sua_chave_http_secreta
API_KEY_WS=sua_chave_websocket_secreta

# Configuração do PostgreSQL
POSTGRES_USER=sensoruser
POSTGRES_PASSWORD=sensorpass
POSTGRES_DB=sensordb
DATABASE_URL=postgresql://sensoruser:sensorpass@db:5432/sensordb

# Limite de conexões WebSocket por chave (0 = ilimitado)
MAX_WS_CONNECTIONS_PER_KEY=10

# Grafana (opcional)
GF_SECURITY_ADMIN_PASSWORD=admin123
```

### 3. Execute com Docker Compose

```bash
# Iniciar todos os serviços
docker-compose up -d

# Ver logs em tempo real
docker-compose logs -f

# Parar os serviços
docker-compose down
```

### 4. Acesse os Serviços

- **API Sensor**: http://localhost:8000
- **Grafana Dashboard**: http://localhost:3000
  - Usuário: `admin`
  - Senha: valor definido em `GF_SECURITY_ADMIN_PASSWORD`

## 📡 API Endpoints

### 🌡️ Envio de Dados de Sensores

**POST** `/api/temperature_reading`

- **Descrição**: Recebe dados de sensores (temperatura, umidade e pressão)
- **Autenticação**: Header `X-API-Key` obrigatório
- **Content-Type**: `application/json`

**Exemplo de Requisição:**
```bash
curl -X POST "http://localhost:8000/api/temperature_reading" \
  -H "X-API-Key: sua_chave_http_secreta" \
  -H "Content-Type: application/json" \
  -d '{
    "temperature": 25.5,
    "humidity": 60.2,
    "pressure": 1012.5,
    "sensor_id": "sensor_001"
  }'
```

**Resposta (201 Created):**
```json
{
  "id": 123,
  "temperature": 25.5,
  "humidity": 60.2,
  "pressure": 1012.5,
  "date_recorded": "2025-07-12",
  "time_recorded": "14:30:45",
  "sensor_id": "sensor_001",
  "client_ip": "192.168.1.100"
}
```

### 🔌 WebSocket para Tempo Real

**WebSocket** `/ws/sensor_updates?api-key=sua_chave_websocket_secreta`

- **Descrição**: Recebe dados em tempo real conforme chegam na API
- **Autenticação**: Query parameter `api-key` obrigatório

**Exemplo JavaScript:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/sensor_updates?api-key=sua_chave_websocket_secreta');

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('Novos dados do sensor:', data);
    // Atualizar dashboard em tempo real
};
```

## 🏗️ Estrutura dos Dados

### Payload de Entrada
```json
{
  "temperature": 25.5,    // Temperatura em Celsius
  "humidity": 60.2,       // Umidade relativa em %
  "pressure": 1012.5,     // Pressão atmosférica em hPa
  "sensor_id": "sensor_001" // Identificador único do sensor
}
```

### Resposta Completa
```json
{
  "id": 123,                    // ID único no banco de dados
  "temperature": 25.5,          // Temperatura recebida
  "humidity": 60.2,             // Umidade recebida
  "pressure": 1012.5,           // Pressão recebida
  "date_recorded": "2025-07-12", // Data de registro (fuso horário Brasil)
  "time_recorded": "14:30:45",   // Hora de registro (fuso horário Brasil)
  "sensor_id": "sensor_001",     // ID do sensor
  "client_ip": "192.168.1.100"  // IP do cliente que enviou
}
```

## 📊 Grafana Dashboard

O Grafana está pré-configurado para conectar automaticamente ao PostgreSQL e visualizar:

- **Temperatura ao longo do tempo**
- **Umidade relativa**
- **Pressão atmosférica**
- **Dados por sensor**
- **Estatísticas em tempo real**

### Configuração Automática
- Datasource PostgreSQL configurado automaticamente
- Dashboards prontos para usar
- Atualizações em tempo real dos dados

## 🎯 Grafana Provisioning (Configuração Automática)

### 📋 Como funciona o "Manual de Instruções"

O Grafana está configurado para conectar **automaticamente** ao PostgreSQL através de um processo chamado **Provisioning**. É como se déssemos um "manual de instruções" para o Grafana seguir quando ele inicia.

#### 🗂️ Estrutura do Provisioning:
```
grafana/
└── provisioning/
    └── datasources/
        └── datasource.yml      # 🔗 Conecta automaticamente ao PostgreSQL
```

#### 🔧 Como o Docker Compose conecta tudo:
```yaml
grafana:
  env_file: - .env                    # 🔑 "Cola" com senhas e credenciais
  volumes:
    - ./grafana/provisioning:/etc/grafana/provisioning  # 📋 "Manual de Instruções"
```

#### 🎯 O que acontece automaticamente:

1. **Grafana inicia** → Lê o arquivo `datasource.yml`
2. **Encontra variáveis** → `${POSTGRES_USER}`, `${POSTGRES_PASSWORD}`, `${POSTGRES_DB}`
3. **Consulta o .env** → Substitui as variáveis pelos valores reais
4. **Conecta ao banco** → Cria automaticamente a fonte de dados "PostgreSQL Sensores"
5. **Pronto para usar** → Você pode criar seus próprios dashboards

### 🚀 Resultado Final:
Quando você acessa `http://localhost:3000` pela primeira vez:
- ✅ Fonte de dados PostgreSQL já configurada e conectada
- ✅ Pronto para criar dashboards personalizados
- ✅ Acesso direto à tabela `data` com todos os campos dos sensores
- ✅ Dados atualizados em tempo real conforme chegam na API

### 📊 Criando seus Dashboards:
1. Acesse `http://localhost:3000`
2. Login: `admin` / Senha: valor do `.env` (`GF_SECURITY_ADMIN_PASSWORD`)
3. Clique em "+" → "Dashboard" → "Add new panel"
4. A fonte "PostgreSQL Sensores" já estará disponível
5. Use queries como:
   ```sql
   SELECT date_recorded + time_recorded as time, temperature 
   FROM data 
   WHERE $__timeFilter(date_recorded + time_recorded)
   ```

**Não precisa configurar conexão - só criar os gráficos que você quiser!** �

## � Segurança

- **API Keys Duplas**: Separação entre HTTP e WebSocket
- **Limite de Conexões**: Controle configurável por API Key
- **Validação de Dados**: Modelos Pydantic para validação automática
- **Logs Detalhados**: Rastreamento completo de todas as operações

## 🐳 Docker Services

| Serviço | Porta | Descrição |
|---------|-------|-----------|
| **api** | 8000 | API FastAPI principal |
| **db** | 5432 | PostgreSQL database |
| **grafana** | 3000 | Dashboard e visualização |

## 📝 Logs e Monitoramento

```bash
# Ver logs de todos os serviços
docker-compose logs -f

# Ver logs apenas da API
docker-compose logs -f api

# Ver logs do banco de dados
docker-compose logs -f db

# Ver logs do Grafana
docker-compose logs -f grafana
```

## 📝 Desenvolvimento

### Estrutura do Código
- **Modular**: Cada funcionalidade em seu próprio módulo
- **Testável**: Módulos independentes facilitam testes
- **Escalável**: Fácil adicionar novas funcionalidades
- **Manutenível**: Código organizado e bem documentado

### Contribuindo
1. Fork o projeto
2. Crie sua feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo `LICENSE` para mais detalhes.

---

**Desenvolvido com ❤️ por João Paulo**
