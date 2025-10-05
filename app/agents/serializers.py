from rest_framework import serializers
from .models import Agent, Conversation, Message, Event


class AgentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Agent
        fields = ['id', 'name', 'agent_type', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ['id', 'role', 'content', 'created_at']
        read_only_fields = ['id', 'created_at']


class ConversationSerializer(serializers.ModelSerializer):
    agent = AgentSerializer(read_only=True)
    messages = MessageSerializer(many=True, read_only=True)
    message_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            'id', 'agent', 'title', 'messages',
            'message_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_message_count(self, obj):
        return obj.messages.count()


class ConversationListSerializer(serializers.ModelSerializer):
    """Serializer ligero para listar conversaciones"""
    agent_name = serializers.CharField(source='agent.name', read_only=True)
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            'id', 'agent_name', 'title',
            'last_message', 'updated_at'
        ]

    def get_last_message(self, obj):
        last_msg = obj.messages.last()
        if last_msg:
            return {
                'role': last_msg.role,
                'content': last_msg.content[:100],
                'created_at': last_msg.created_at
            }
        return None


class ChatMessageSerializer(serializers.Serializer):
    """Serializer para enviar mensajes al chat"""
    message = serializers.CharField(required=True)


class EventSerializer(serializers.ModelSerializer):
    """Serializer para eventos guardados"""
    user_email = serializers.EmailField(source='user.email', read_only=True)
    conversation_title = serializers.CharField(source='conversation.title', read_only=True)

    class Meta:
        model = Event
        fields = [
            'id', 'user_email', 'conversation_title', 'event_name',
            'event_date', 'location_name', 'latitude', 'longitude',
            'weather_data', 'temperature', 'precipitation', 'wind_speed',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
