# Space Apps - Weather Agent Backend

Backend de Django con agente de clima espacial usando Google Gemini.

## Requisitos

- Docker y Docker Compose
- API Key de Google ([obtener aquí](https://aistudio.google.com/app/apikey))

## Configuración

1. **Copiar variables de entorno**:
```bash
cp .env.example .env
```

2. **Editar `.env`**:
```env
GOOGLE_API_KEY=tu-api-key-de-google
GEMINI_MODEL=gemini-2.0-flash-exp
```

3. **Iniciar el proyecto**:
```bash
docker-compose up --build
```

4. **Crear superusuario**:
```bash
docker-compose exec app python manage.py createsuperuser
```

## Endpoints

- **API Docs**: http://localhost:8080/api/docs/
- **Admin**: http://localhost:8080/admin/

### Uso básico

```bash
# Crear conversación
POST /api/conversations/

# Enviar mensaje
POST /api/conversations/{id}/send_message/
{
  "message": "¿Cómo está el clima espacial hoy?"
}

# Ver historial
GET /api/conversations/{id}/history/
```

## Tecnologías

- Django 5.1 + DRF
- Google Gemini AI
- PostgreSQL
- Docker
