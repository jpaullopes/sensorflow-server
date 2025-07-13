# 💾 Persistência de Dados - SensorFlow Server

## 🔧 Configuração de Volumes Persistentes

O SensorFlow Server está configurado com volumes Docker para garantir que os dados sejam mantidos mesmo após reinicialização do sistema.

### 📊 Volumes Configurados

| Volume | Localização | Função |
|--------|-------------|---------|
| `postgres_data` | `/var/lib/postgresql/data` | Dados do PostgreSQL |
| `grafana_data` | `/var/lib/grafana` | Configurações e dashboards do Grafana |

### 🚀 Configuração Automática

Ao executar `docker-compose up -d`, os seguintes elementos são automaticamente configurados:

#### 🗄️ PostgreSQL
- **Persistência**: Todos os dados de sensores são mantidos permanentemente
- **Localização**: Volume `postgres_data` 
- **Backup automático**: Os dados sobrevivem a reinicializações

#### 📊 Grafana
- **Dashboards**: Carregamento automático do dashboard "Dashboard Sensores IoT"
- **Datasource**: Conexão automática com PostgreSQL
- **Configurações**: Preservadas entre reinicializações
- **Usuário padrão**: admin/sua_senha (definida no .env)

### 📋 Dashboard Pré-configurado

O dashboard "Dashboard Sensores IoT" inclui:

- **📡 Última Temperatura**: Valor mais recente registrado
- **💧 Última Umidade**: Medidor gauge com último valor
- **📊 Média de Temperatura por Sensor**: Gráfico de barras comparativo
- **🔢 Quantidade de Sensores**: Contagem de sensores ativos
- **📈 Evolução das Métricas**: Gráfico temporal de todas as métricas
- **📝 Últimas Leituras**: Tabela com os 10 registros mais recentes

### 🔄 Comandos de Gerenciamento

```bash
# Iniciar com persistência
docker-compose up -d

# Ver logs para verificar funcionamento
docker-compose logs -f

# Parar mantendo dados
docker-compose down

# Backup manual dos volumes (opcional)
docker run --rm -v postgres_data:/data -v $(pwd):/backup ubuntu tar czf /backup/postgres_backup.tar.gz /data

# Restaurar backup (opcional)
docker run --rm -v postgres_data:/data -v $(pwd):/backup ubuntu tar xzf /backup/postgres_backup.tar.gz -C /
```

### 🎯 Primeira Execução

1. **Execute a stack**: `docker-compose up -d`
2. **Acesse o Grafana**: http://localhost:3000 (admin/sua_senha)
3. **Dashboard automático**: Já estará disponível na página inicial
4. **Envie dados**: Use a API para popular o dashboard

### ⚠️ Importante

- Os dados são persistentes entre reinicializações
- O dashboard é criado automaticamente na primeira execução
- A conexão PostgreSQL é configurada automaticamente
- Não é necessário configuração manual no Grafana
