# 📊 Queries SQL Úteis para Grafana

## 🌡️ Temperatura ao Longo do Tempo
```sql
SELECT 
  date_recorded + time_recorded as time,
  temperature,
  sensor_id
FROM data 
WHERE $__timeFilter(date_recorded + time_recorded)
ORDER BY time
```

## 💧 Umidade Relativa
```sql
SELECT 
  date_recorded + time_recorded as time,
  humidity,
  sensor_id
FROM data 
WHERE $__timeFilter(date_recorded + time_recorded)
ORDER BY time
```

## 🌪️ Pressão Atmosférica
```sql
SELECT 
  date_recorded + time_recorded as time,
  pressure,
  sensor_id
FROM data 
WHERE $__timeFilter(date_recorded + time_recorded)
ORDER BY time
```

## 📈 Últimas Leituras (Tabela)
```sql
SELECT 
  sensor_id,
  temperature,
  humidity,
  pressure,
  date_recorded,
  time_recorded,
  client_ip
FROM data 
ORDER BY id DESC 
LIMIT 10
```

## 📊 Estatísticas por Sensor
```sql
SELECT 
  sensor_id,
  COUNT(*) as total_readings,
  AVG(temperature) as avg_temp,
  MIN(temperature) as min_temp,
  MAX(temperature) as max_temp,
  AVG(humidity) as avg_humidity,
  AVG(pressure) as avg_pressure
FROM data 
WHERE $__timeFilter(date_recorded + time_recorded)
GROUP BY sensor_id
ORDER BY total_readings DESC
```

## 🕒 Leituras por Hora
```sql
SELECT 
  DATE_TRUNC('hour', date_recorded + time_recorded) as time,
  COUNT(*) as readings_count
FROM data 
WHERE $__timeFilter(date_recorded + time_recorded)
GROUP BY DATE_TRUNC('hour', date_recorded + time_recorded)
ORDER BY time
```

## 🎯 Como Usar no Grafana:

1. **Acesse:** http://localhost:3000
2. **Login:** admin / senha do .env
3. **Criar Dashboard:** + → Dashboard → Add new panel
4. **Fonte de Dados:** "PostgreSQL Sensores" (já configurado)
5. **Copie uma query** acima no campo SQL
6. **Configure visualização** conforme desejar
7. **Salve o painel**

## 💡 Dicas:
- Use `$__timeFilter()` para filtros automáticos de tempo
- Campo `time` deve combinar `date_recorded + time_recorded`
- Grafana detecta automaticamente séries temporais
- Para gráficos de linha, use `time` como campo de tempo
- Para tabelas, remova `$__timeFilter()` e use `LIMIT`
