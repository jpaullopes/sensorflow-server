# Estrutura Modular do SensorFlow Server

## 📁 Nova Organização dos Arquivos

### **Arquivo Principal**
- `main.py` - Ponto de entrada simplificado da aplicação

### **Módulos de Configuração**
- `config.py` - Variáveis de ambiente e estado da aplicação
- `logger_config.py` - Configuração do sistema de logs coloridos

### **Módulos de Dados**
- `models.py` - Modelos SQLAlchemy (banco) e Pydantic (API)
- `database.py` - Configuração e conexão com o banco de dados

### **Módulos de Funcionalidades**
- `auth.py` - Autenticação e verificação de API keys
- `websocket_manager.py` - Gerenciamento de conexões WebSocket

### **Módulos de Rotas**
- `routes/__init__.py` - Exportação dos roteadores
- `routes/api_routes.py` - Endpoints HTTP da API
- `routes/websocket_routes.py` - Endpoints WebSocket

### **Arquivos de Suporte**
- `test_imports.py` - Script para testar importações
- `requirements.txt` - Dependências Python
- `docker-compose.yml` - Configuração Docker

## 🚀 Melhorias Implementadas

### **1. Modularização Completa**
- ✅ Código dividido em módulos específicos por responsabilidade
- ✅ Facilita manutenção e desenvolvimento colaborativo
- ✅ Imports organizados e dependências claras

### **2. Remoção do Frontend**
- ❌ Removido `templates/index.html`
- ❌ Removidas dependências do Jinja2Templates
- ✅ API focada apenas no backend (dados dos sensores)

### **3. Separação de Responsabilidades**
- **Config**: Centralizou todas as configurações
- **Auth**: Isolou lógica de autenticação
- **Database**: Separou configuração do banco de dados
- **WebSocket**: Modularizou gerenciamento de conexões
- **Routes**: Organizou endpoints em arquivos separados

### **4. Benefícios da Nova Estrutura**
- 🔧 **Manutenibilidade**: Cada módulo tem uma responsabilidade clara
- 🧪 **Testabilidade**: Módulos podem ser testados independentemente
- 📈 **Escalabilidade**: Fácil adicionar novas funcionalidades
- 🔄 **Reutilização**: Módulos podem ser reutilizados em outros projetos
- 📖 **Legibilidade**: Código mais organizado e fácil de entender

## 💻 Como Usar

### **Executar a Aplicação**
```bash
python main.py
# ou
uvicorn main:app --host 0.0.0.0 --port 8000
```

### **Testar Importações**
```bash
python test_imports.py
```

### **Docker (Recomendado)**
```bash
docker-compose up --build
```

## 🌟 Funcionalidades Mantidas

Todas as funcionalidades originais foram preservadas:
- ✅ Recebimento de dados via HTTP POST
- ✅ Broadcast em tempo real via WebSocket
- ✅ Autenticação por API Key
- ✅ Limite de conexões WebSocket por chave
- ✅ Logs coloridos e informativos
- ✅ Tratamento robusto de erros de banco
- ✅ Suporte a múltiplos workers
- ✅ Fuso horário Brasil (São Paulo)

A única mudança é que agora **não há mais interface web** - a API é puramente backend para receber e distribuir dados dos sensores.
