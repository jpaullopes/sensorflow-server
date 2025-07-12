# SensorFlow Server

![Linguagem](https://img.shields.io/badge/Linguagem-python-green.svg)
![Badge de Versão](https://img.shields.io/badge/version-1.0.0-blue)
![Licença](https://img.shields.io/badge/Licen%C3%A7a-MIT-yellow.svg)

Uma aplicação de backend desenvolvida em Python com FastAPI, projetada para coletar, armazenar e distribuir dados de sensores em tempo real. A arquitetura é otimizada para ser resiliente e escalável, utilizando Docker para fácil implantação.

## 🚀 Funcionalidades

- **Coleta de Dados via API REST**: Recebe dados de sensores (temperatura, umidade e pressão) através de um endpoint HTTP POST seguro.
- **Distribuição em Tempo Real com WebSockets**: Transmite instantaneamente os dados recebidos para todos os clientes conectados via WebSocket, ideal para dashboards e monitoramento ao vivo.
- **Armazenamento Persistente**: Salva todas as leituras de sensores em um banco de dados PostgreSQL, garantindo a integridade e a disponibilidade dos dados históricos.
- **Interface Web de Demonstração**: Inclui uma página web estática (`index.html`) que demonstra a visualização dos dados em tempo real, simulando um dashboard.
- **Segurança**: Protege os endpoints com chaves de API (API Keys), tanto para requisições HTTP quanto para conexões WebSocket.
- **Implantação Flexível com Docker**:
    - **Modo HTTP Simples**: Permite a execução da aplicação de forma isolada em um contêiner Docker, acessível via HTTP.
    - **Modo HTTPS com Proxy Reverso**: Utiliza Docker Compose para orquestrar a aplicação junto com Nginx e Let's Encrypt, provendo proxy reverso, encriptação SSL/TLS (HTTPS) e renovação automática de certificados.

## 🛠️ Tecnologias Utilizadas

- **Backend**: Python, FastAPI
- **Banco de Dados**: PostgreSQL (via SQLAlchemy)
- **Comunicação em Tempo Real**: WebSockets
- **Contêineres**: Docker, Docker Compose
- **Proxy Reverso e SSL**: Nginx, Let's Encrypt
- **Frontend (Demo)**: HTML, Tailwind CSS, Chart.js

## 📋 Pré-requisitos

Antes de começar, garanta que você tenha as seguintes ferramentas instaladas:
- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

## ⚙️ Instalação e Execução

Siga as instruções abaixo para executar o projeto.

### 1. Clone o Repositório

```bash
git clone [https://github.com/thalyssondev/sensorflow-server.git](https://github.com/thalyssondev/sensorflow-server.git)
cd sensorflow-server
```

### 2. Configure as Variáveis de Ambiente

Crie um arquivo chamado `.env` na raiz do projeto. Substitua os valores pelas suas próprias chaves e configurações.

```dotenv
# .env

# Chaves de API para proteger os endpoints
API_KEY=SUA_CHAVE_DE_API_SECRETA_HTTP
API_KEY_WS=SUA_CHAVE_DE_API_SECRETA_WEBSOCKET

# URL de conexão com o banco de dados PostgreSQL
# Formato: postgresql://USUARIO:SENHA@HOST:PORTA/NOME_DO_BANCO
DATABASE_URL=postgresql://user:password@db:5432/sensordb

# Limite de conexões WebSocket por chave (0 para ilimitado)
MAX_WS_CONNECTIONS_PER_KEY=5
```

### 3. Métodos de Execução

Você pode executar a aplicação de duas maneiras:

---

#### Opção A: Execução com Docker (Servidor HTTP)

Este método irá construir a imagem Docker da aplicação e executá-la em um contêiner, expondo a porta 8000. O servidor estará acessível via **HTTP**.

1.  **Construa a imagem Docker:**
    ```bash
    docker build -t sensorflow-server .
    ```

2.  **Execute o contêiner:**
    ```bash
    docker run -d -p 8000:8000 --env-file .env --name sensorflow-app sensorflow-server
    ```

A aplicação estará disponível em `http://localhost:8000`.

---

#### Opção B: Execução com Docker Compose (Servidor HTTPS com Proxy Reverso)

Este método é ideal para produção. Ele utiliza o arquivo `docker-compose.yml` para orquestrar a aplicação junto com um contêiner Nginx e um assistente Let's Encrypt. O resultado é um serviço seguro, acessível via **HTTPS**, com gerenciamento automático de certificados SSL.

**Importante**: Para que a geração do certificado SSL funcione, você deve ter um nome de domínio (ex: `sensorflow.zapto.org`) apontando para o endereço IP público do seu servidor.

1.  **Atualize o `docker-compose.yml` (se necessário):**
    O arquivo `docker-compose.yml` já está pré-configurado para o domínio `sensorflow.zapto.org`. Se você estiver usando um domínio diferente, atualize as seguintes variáveis de ambiente no arquivo:
    ```yaml
    services:
      api:
        # ...
        environment:
          - VIRTUAL_HOST=seu-dominio.com
          - VIRTUAL_PORT=8000
          - LETSENCRYPT_HOST=seu-dominio.com
          - LETSENCRYPT_EMAIL=seu-email@exemplo.com
    ```

2.  **Inicie os serviços:**
    Execute o Docker Compose em modo "detached" (`-d`):
    ```bash
    docker-compose up -d
    ```

O Docker Compose irá baixar as imagens necessárias (Nginx, etc.), construir a imagem da sua aplicação e iniciar todos os contêineres. O assistente Let's Encrypt irá gerar automaticamente o certificado SSL.

A aplicação estará disponível em `https://sensorflow.zapto.org` (ou o domínio que você configurou).

## 📡 Endpoints da API

### Endpoint HTTP

-   **POST** `/api/temperature_reading`
    -   **Descrição**: Envia uma nova leitura de dados dos sensores.
    -   **Header Obrigatório**: `X-API-Key: SUA_CHAVE_DE_API_SECRETA_HTTP`
    -   **Corpo da Requisição (JSON)**:
        ```json
        {
          "temperature": 25.5,
          "humidity": 60.2,
          "pressure": 1012.5,
          "sensor_id": "sensor-01"
        }
        ```

### Endpoint WebSocket

-   **GET** `/ws/sensor_updates`
    -   **Descrição**: Conecta-se ao servidor para receber atualizações de dados de sensores em tempo real.
    -   **Parâmetro de Query Obrigatório**: `?api-key=SUA_CHAVE_DE_API_SECRETA_WEBSOCKET`
    -   **URL de Conexão (Exemplo)**: `wss://sensorflow.zapto.org/ws/sensor_updates?api-key=SUA_CHAVE_DE_API_SECRETA_WEBSOCKET`

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo `LICENSE` para mais detalhes.
