# Space Apps - Weather Agent Backend

Backend de Django con agente de clima espacial usando Claude (Anthropic).

## 🚀 Características

- **Agente de Clima Espacial**: Especializado en meteorología y clima espacial
- **Claude AI Integration**: Usando Anthropic Claude 3.5 Sonnet
- **REST API**: Endpoints para conversaciones con el agente
- **PostgreSQL**: Base de datos para persistencia
- **Docker**: Ambiente containerizado completo

## 📋 Requisitos Previos

- Docker y Docker Compose
- API Key de Anthropic ([obtener aquí](https://console.anthropic.com/))

## ⚙️ Configuración

1. **Clonar y configurar variables de entorno**:
```bash
cp .env.example .env
```

2. **Editar `.env` con tus valores**:
```env
ANTHROPIC_API_KEY=tu-api-key-de-anthropic
```

3. **Construir y levantar los contenedores**:
```bash
docker-compose up --build
```

4. **Crear superusuario** (en otra terminal):
```bash
docker-compose exec app python manage.py createsuperuser
```

## 🌐 Endpoints Disponibles

### Documentación API
- **Swagger UI**: http://localhost:8080/api/docs/
- **Admin Panel**: http://localhost:8080/admin/
- **pgAdmin**: http://localhost:5050/

### API Endpoints

#### Listar agentes disponibles
```bash
GET /api/agents/
```

#### Crear nueva conversación
```bash
POST /api/conversations/
```

#### Enviar mensaje al agente
```bash
POST /api/conversations/{id}/send_message/
Content-Type: application/json

{
  "message": "¿Cómo está el clima espacial hoy?"
}
```

#### Obtener historial de conversación
```bash
GET /api/conversations/{id}/history/
```

## 🤖 System Prompt del Agente

El agente está configurado con un system prompt especializado en:

- Predicciones meteorológicas terrestres
- Clima espacial y actividad solar
- Tormentas geomagnéticas y su impacto
- Radiación espacial
- Efectos del clima espacial en satélites y comunicaciones
- Fenómenos atmosféricos relacionados con eventos espaciales

Puedes modificar el system prompt en `app/agents/services.py`.

## 🏗️ Estructura del Proyecto

```
space-apps-backend/
├── app/
│   ├── agents/              # App de agentes de IA
│   │   ├── models.py       # Agent, Conversation, Message
│   │   ├── services.py     # Integración con Claude API
│   │   ├── views.py        # API ViewSets
│   │   ├── serializers.py  # DRF Serializers
│   │   └── admin.py        # Django Admin
│   └── core/               # Configuración del proyecto
├── docker-compose.yaml
├── Dockerfile
└── requirements.txt
```

## 🔧 Desarrollo

### Ejecutar migraciones
```bash
docker-compose exec app python manage.py makemigrations
docker-compose exec app python manage.py migrate
```

### Crear app nueva
```bash
docker-compose exec app python manage.py startapp nombre_app
```

### Ver logs
```bash
docker-compose logs -f app
```

## 📚 Tecnologías

- Django 5.1+
- Django REST Framework
- Anthropic Claude API
- PostgreSQL 13
- Docker & Docker Compose
- drf-spectacular (OpenAPI/Swagger)

## 🔐 Seguridad

- Nunca compartas tu `ANTHROPIC_API_KEY`
- El archivo `.env` está en `.gitignore`
- Usa `.env.example` como plantilla

## 📄 Licencia

MIT
