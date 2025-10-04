from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Agent, Conversation, Message
from .serializers import (
    AgentSerializer,
    ConversationSerializer,
    ConversationListSerializer,
    ChatMessageSerializer
)
from .services import WeatherAgentService


class AgentViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet para listar agentes disponibles"""
    queryset = Agent.objects.filter(is_active=True)
    serializer_class = AgentSerializer
    permission_classes = [IsAuthenticated]


class ConversationViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar conversaciones"""
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Conversation.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action == 'list':
            return ConversationListSerializer
        return ConversationSerializer

    def create(self, request, *args, **kwargs):
        """Crear nueva conversación con agente de clima"""
        conversation = WeatherAgentService.create_conversation(request.user)
        serializer = self.get_serializer(conversation)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def send_message(self, request, pk=None):
        """
        Enviar mensaje al agente y obtener respuesta

        POST /api/conversations/{id}/send_message/
        {
            "message": "¿Cómo está el clima espacial hoy?"
        }
        """
        conversation = self.get_object()
        serializer = ChatMessageSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        user_message = serializer.validated_data['message']

        # Procesar mensaje y obtener respuesta
        response_message = WeatherAgentService.process_user_message(
            conversation,
            user_message
        )

        return Response({
            'user_message': user_message,
            'assistant_message': response_message,
            'conversation_id': conversation.id
        })

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """
        Obtener historial completo de la conversación

        GET /api/conversations/{id}/history/
        """
        conversation = self.get_object()
        history = WeatherAgentService.get_conversation_history(conversation)

        return Response({
            'conversation_id': conversation.id,
            'agent': conversation.agent.name,
            'messages': history
        })
