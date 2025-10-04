"""
Servicios para gestionar agentes de IA usando Google Gemini
"""

import os
from typing import Dict, List
from google import genai
from django.conf import settings
from .models import Agent, Conversation, Message


class WeatherAgentService:
    """Servicio para el agente de clima usando claude-agent-sdk"""

    SYSTEM_PROMPT = """Eres un asistente experto en meteorología y clima espacial.

Tu especialidad incluye:
- Predicciones meteorológicas terrestres
- Clima espacial y actividad solar
- Tormentas geomagnéticas y su impacto
- Radiación espacial
- Efectos del clima espacial en satélites y comunicaciones
- Fenómenos atmosféricos relacionados con eventos espaciales

Debes proporcionar información precisa, científica y comprensible. Cuando no tengas datos
en tiempo real, indícalo claramente y ofrece información general sobre el tema.

Siempre responde en el idioma en el que te hablen.
"""

    @classmethod
    def get_or_create_agent(cls) -> Agent:
        """Obtiene o crea el agente de clima"""
        agent, created = Agent.objects.get_or_create(
            agent_type="weather",
            defaults={
                "name": "Weather & Space Climate Agent",
                "system_prompt": cls.SYSTEM_PROMPT,
                "is_active": True,
            },
        )
        return agent

    @classmethod
    def create_conversation(cls, user) -> Conversation:
        """Crea una nueva conversación con el agente de clima"""
        agent = cls.get_or_create_agent()
        conversation = Conversation.objects.create(
            user=user, agent=agent, title="Weather Consultation"
        )
        return conversation

    @classmethod
    def add_message(
        cls, conversation: Conversation, role: str, content: str
    ) -> Message:
        """Añade un mensaje a la conversación"""
        message = Message.objects.create(
            conversation=conversation, role=role, content=content
        )
        return message

    @classmethod
    def get_conversation_history(cls, conversation: Conversation) -> List[Dict]:
        """Obtiene el historial de la conversación en formato para LLM"""
        messages = conversation.messages.all().order_by("created_at")
        history = []

        for msg in messages:
            history.append({"role": msg.role, "content": msg.content})

        return history

    @classmethod
    def _initialize_gemini(cls):
        """
        Inicializa el cliente de Google Gemini

        Returns:
            Cliente configurado de Gemini
        """
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY no está configurada")

        client = genai.Client(api_key=api_key)
        return client

    @classmethod
    def process_user_message(cls, conversation: Conversation, user_message: str) -> str:
        """
        Procesa un mensaje del usuario y genera una respuesta usando Google Gemini
        """
        # Validar mensaje
        if not user_message or not user_message.strip():
            raise ValueError("El mensaje no puede estar vacío")

        # Guardar mensaje del usuario
        cls.add_message(conversation, "user", user_message)

        try:
            # Inicializar cliente Gemini
            client = cls._initialize_gemini()
            model_name = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash-exp")

            # Obtener historial para contexto
            history = cls.get_conversation_history(conversation)

            # Preparar contenido para Gemini
            contents = []

            # Incluir system prompt como primer mensaje del sistema
            if len(history) == 1:  # Solo el mensaje actual
                contents.append(genai.types.Content(
                    role="user",
                    parts=[genai.types.Part(text=f"{conversation.agent.system_prompt}\n\n{user_message}")]
                ))
            else:
                # Agregar historial (excluir el último)
                for msg in history[:-1]:
                    role = "user" if msg["role"] == "user" else "model"
                    contents.append(genai.types.Content(
                        role=role,
                        parts=[genai.types.Part(text=msg["content"])]
                    ))
                # Agregar mensaje actual
                contents.append(genai.types.Content(
                    role="user",
                    parts=[genai.types.Part(text=user_message)]
                ))

            # Generar respuesta
            response = client.models.generate_content(
                model=model_name,
                contents=contents
            )

            assistant_message = response.text

            # Guardar respuesta del asistente
            cls.add_message(conversation, "assistant", assistant_message)

            return assistant_message

        except ValueError as e:
            raise
        except Exception as e:
            error_msg = f"Error al usar Google Gemini: {str(e)}"
            print(error_msg)
            raise Exception(error_msg)


class MultiAgentService:
    """
    Servicio base para crear múltiples agentes con claude-agent-sdk
    """

    @classmethod
    def create_custom_agent(
        cls, agent_type: str, name: str, system_prompt: str, user
    ) -> Conversation:
        """
        Crea un agente personalizado y una conversación

        Args:
            agent_type: Tipo de agente
            name: Nombre del agente
            system_prompt: Prompt del sistema
            user: Usuario que crea la conversación

        Returns:
            Nueva conversación con el agente
        """
        agent, created = Agent.objects.get_or_create(
            agent_type=agent_type,
            defaults={
                "name": name,
                "system_prompt": system_prompt,
                "is_active": True,
            },
        )

        conversation = Conversation.objects.create(
            user=user, agent=agent, title=f"{name} Consultation"
        )

        return conversation

    @classmethod
    def chat(cls, conversation: Conversation, message: str) -> str:
        """
        Envía un mensaje y obtiene respuesta usando Google Gemini

        Args:
            conversation: Conversación activa
            message: Mensaje del usuario

        Returns:
            Respuesta del agente
        """
        if not message or not message.strip():
            raise ValueError("El mensaje no puede estar vacío")

        # Agregar mensaje del usuario
        Message.objects.create(
            conversation=conversation, role="user", content=message
        )

        try:
            # Inicializar Gemini
            api_key = os.environ.get("GOOGLE_API_KEY")
            if not api_key:
                raise ValueError("GOOGLE_API_KEY no está configurada")

            client = genai.Client(api_key=api_key)
            model_name = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash-exp")

            # Cargar historial
            messages_qs = conversation.messages.all().order_by("created_at")
            contents = []

            # Verificar si es el primer mensaje
            if messages_qs.count() == 1:  # Solo el mensaje actual
                contents.append(genai.types.Content(
                    role="user",
                    parts=[genai.types.Part(text=f"{conversation.agent.system_prompt}\n\n{message}")]
                ))
            else:
                # Agregar historial (excluir el último)
                for msg in messages_qs[:-1]:
                    role = "user" if msg.role == "user" else "model"
                    contents.append(genai.types.Content(
                        role=role,
                        parts=[genai.types.Part(text=msg.content)]
                    ))
                # Agregar mensaje actual
                contents.append(genai.types.Content(
                    role="user",
                    parts=[genai.types.Part(text=message)]
                ))

            # Generar respuesta
            response = client.models.generate_content(
                model=model_name,
                contents=contents
            )

            assistant_message = response.text

            # Guardar respuesta
            Message.objects.create(
                conversation=conversation,
                role="assistant",
                content=assistant_message,
            )

            return assistant_message

        except Exception as e:
            error_msg = f"Error en MultiAgentService: {str(e)}"
            print(error_msg)
            raise Exception(error_msg)
