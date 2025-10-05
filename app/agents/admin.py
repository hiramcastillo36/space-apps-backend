from django.contrib import admin
from .models import Agent, Conversation, Message, Event


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ['name', 'agent_type', 'is_active', 'created_at']
    list_filter = ['agent_type', 'is_active']
    search_fields = ['name']
    readonly_fields = ['created_at', 'updated_at']


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ['role', 'content', 'created_at']
    can_delete = False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'agent', 'title', 'created_at']
    list_filter = ['agent', 'created_at']
    search_fields = ['user__email', 'title']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'conversation', 'role', 'content_preview', 'created_at']
    list_filter = ['role', 'created_at']
    search_fields = ['content']
    readonly_fields = ['created_at']

    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content'


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['id', 'event_name', 'user', 'event_date', 'location_name', 'temperature', 'created_at']
    list_filter = ['event_date', 'created_at', 'user']
    search_fields = ['event_name', 'location_name', 'user__email']
    readonly_fields = ['created_at', 'updated_at', 'weather_data']
    fieldsets = [
        ('Información del Evento', {
            'fields': ['user', 'conversation', 'event_name', 'event_date', 'location_name']
        }),
        ('Ubicación', {
            'fields': ['latitude', 'longitude']
        }),
        ('Datos Meteorológicos', {
            'fields': ['temperature', 'precipitation', 'wind_speed', 'weather_data']
        }),
        ('Metadata', {
            'fields': ['created_at', 'updated_at']
        }),
    ]
