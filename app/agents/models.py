from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Agent(models.Model):
    """Modelo para definir agentes especializados"""
    AGENT_TYPES = [
        ('weather', 'Weather Agent'),
        ('general', 'General Agent'),
    ]

    name = models.CharField(max_length=100)
    agent_type = models.CharField(max_length=50, choices=AGENT_TYPES)
    system_prompt = models.TextField(
        help_text="System prompt que define el comportamiento del agente"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'agents'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.get_agent_type_display()})"


class Conversation(models.Model):
    """Conversaciones con los agentes"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversations')
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='conversations')
    title = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'conversations'
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.user.email} - {self.agent.name}"


class Message(models.Model):
    """Mensajes dentro de las conversaciones"""
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System'),
    ]

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'messages'
        ordering = ['created_at']

    def __str__(self):
        return f"{self.role}: {self.content[:50]}"


class Event(models.Model):
    """Eventos mencionados por el usuario con información meteorológica"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='events')
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='events',
        null=True,
        blank=True
    )

    # Información del evento
    event_name = models.CharField(max_length=200, help_text="Nombre o descripción del evento")
    event_date = models.DateTimeField(help_text="Fecha y hora del evento")
    location_name = models.CharField(max_length=200, blank=True, help_text="Nombre del lugar")

    # Coordenadas geográficas
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    # Datos meteorológicos (JSON)
    weather_data = models.JSONField(
        null=True,
        blank=True,
        help_text="Datos meteorológicos completos de la API"
    )

    # Parámetros específicos extraídos
    temperature = models.FloatField(null=True, blank=True, help_text="Temperatura en °C")
    precipitation = models.FloatField(null=True, blank=True, help_text="Precipitación en mm")
    wind_speed = models.FloatField(null=True, blank=True, help_text="Velocidad del viento en km/h")

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'events'
        ordering = ['-event_date']
        indexes = [
            models.Index(fields=['user', 'event_date']),
            models.Index(fields=['event_date']),
        ]

    def __str__(self):
        return f"{self.event_name} - {self.event_date.strftime('%Y-%m-%d %H:%M')}"
