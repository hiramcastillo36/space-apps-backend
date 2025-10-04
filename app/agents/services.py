import os
import requests
from typing import Dict, List
from google import genai
from google.genai import types
from django.conf import settings
from .models import Agent, Conversation, Message


class WeatherAgentService:

    SYSTEM_PROMPT = """
        Eres **skAI**, un asistente meteorológico experto en construir consultas para APIs de predicción del clima (como Meteomatics).
        Tu tarea principal es **guiar al usuario paso a paso** para reunir tres datos esenciales:
        fecha/tiempo, parámetros y ubicación.

        ---

        ### 🎯 OBJETIVO FINAL
        Tu misión termina cuando hayas reunido **toda la información necesaria** para generar una consulta completa de clima.
        En ese momento, debes **llamar a la función `get_weather_data`** con los siguientes argumentos JSON:

        ```json
        {
        "time_range": "[YYYY-MM-DDTHH:MM:SSZ--YYYY-MM-DDTHH:MM:SSZ:PTXH]",
        "parameters": "[variables separadas por coma en formato variable:unidad]",
        "location": "[latitud,longitud]",
        "format": "json"
        }
        ```
    """

    TOOLS = [
        types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="get_space_weather_data",
                    description="Obtiene datos actuales del clima espacial desde una API externa",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "data_type": types.Schema(
                                type=types.Type.STRING,
                                description="Tipo de datos a obtener: 'solar', 'geomagnetic', 'radiation'",
                            )
                        },
                        required=["data_type"]
                    )
                )
            ]
        )
    ]

    @classmethod
    def get_or_create_agent(cls) -> Agent:
        agent, created = Agent.objects.get_or_create(
            agent_type="skAI Weather Agent",
            defaults={
                "name": "skAI Weather Agent",
                "system_prompt": cls.SYSTEM_PROMPT,
                "is_active": True,
            },
        )

        if not created:
            agent.system_prompt = cls.SYSTEM_PROMPT
            agent.save()

        return agent

    @classmethod
    def create_conversation(cls, user) -> Conversation:
        agent = cls.get_or_create_agent()
        conversation = Conversation.objects.create(
            user=user,
            agent=agent,
            title="Weather Consultation"
        )
        return conversation

    @classmethod
    def add_message(cls, conversation: Conversation, role: str, content: str) -> Message:
        return Message.objects.create(conversation=conversation, role=role, content=content)

    @classmethod
    def get_conversation_history(cls, conversation: Conversation) -> List[Dict]:
        messages = conversation.messages.all().order_by("created_at")
        return [{"role": msg.role, "content": msg.content} for msg in messages]

    @classmethod
    def _initialize_gemini(cls):
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY no está configurada")
        return genai.Client(api_key=api_key)

    @classmethod
    def _call_external_api(cls, function_name: str, args: Dict) -> Dict:
        if function_name == "get_space_weather_data":
            data_type = args.get("data_type", "solar")
            api_url = os.environ.get("SPACE_WEATHER_API_URL", "https://api.nasa.gov/DONKI/FLR")
            api_key = os.environ.get("NASA_API_KEY", "DEMO_KEY")

            try:
                response = requests.get(api_url, params={"api_key": api_key}, timeout=10)
                response.raise_for_status()
                return {"success": True, "data": response.json()}
            except Exception as e:
                return {"success": False, "error": str(e)}

        return {"success": False, "error": "Función no reconocida"}

    @classmethod
    def process_user_message(cls, conversation: Conversation, user_message: str) -> str:
        if not user_message or not user_message.strip():
            raise ValueError("El mensaje no puede estar vacío")

        cls.add_message(conversation, "user", user_message)

        try:
            client = cls._initialize_gemini()
            model_name = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash-exp")

            history = cls.get_conversation_history(conversation)
            contents = []

            # Cargar historial correctamente
            for msg in history:
                role = "user" if msg["role"] == "user" else "model"
                contents.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))

            # Generar respuesta inicial
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=conversation.agent.system_prompt,  # ✅ system prompt correcto
                    tools=cls.TOOLS,
                ),
            )

            # Verificar si el modelo quiere llamar una función
            candidate = response.candidates[0].content.parts[0]
            if hasattr(candidate, "function_call") and candidate.function_call:
                function_call = candidate.function_call
                function_name = function_call.name
                function_args = dict(function_call.args)

                function_result = cls._call_external_api(function_name, function_args)

                contents.append(response.candidates[0].content)
                contents.append(
                    types.Content(
                        parts=[
                            types.Part(
                                function_response=types.FunctionResponse(
                                    name=function_name,
                                    response=function_result
                                )
                            )
                        ]
                    )
                )

                # Generar respuesta final con el resultado de la función
                final_response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=conversation.agent.system_prompt,  # ✅ mantener el prompt
                        tools=cls.TOOLS,
                    ),
                )
                assistant_message = final_response.text
            else:
                assistant_message = response.text

            cls.add_message(conversation, "assistant", assistant_message)
            return assistant_message

        except Exception as e:
            error_msg = f"Error al usar Google Gemini: {str(e)}"
            print(error_msg)
            raise Exception(error_msg)
