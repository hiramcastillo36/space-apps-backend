import os
import requests
from typing import Dict, List
from google import genai
from google.genai import types
from django.conf import settings
from .models import Agent, Conversation, Message
import googlemaps


class WeatherAgentService:

    SYSTEM_PROMPT = """
        Eres **skAI**, un asistente meteorológico experto en construir consultas para APIs de predicción del clima.
        Tu tarea principal es **guiar al usuario paso a paso** para reunir tres datos esenciales:
        fecha/tiempo, parámetros y ubicación.

        ---

        ### 🧠 PROCESO
        1. Pregunta por cada dato uno por uno si no se proporcionan.
        2. Para la ubicación, el usuario puede darte un nombre de lugar (ej: "el clima en Londres").
        3. Si el usuario te da un nombre de lugar, **DEBES usar la función `get_coordinates_from_address`** para obtener la latitud y longitud.
        4. No inventes coordenadas. Siempre usa la herramienta si no tienes las coordenadas numéricas.

        ### 🎯 OBJETIVO FINAL
        Tu misión termina cuando hayas reunido **toda la información necesaria** (fecha, parámetros y coordenadas).
        En ese momento, debes **llamar a la función `get_weather_data`** con los argumentos JSON correctos.
    """

    TOOLS = [
        types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="get_weather_data",
                    description="Obtiene datos meteorológicos desde la API de Meteomatics. Requiere fecha/tiempo en formato ISO (YYYY-MM-DDTHH:MM:SSZ), parámetros meteorológicos (ej: 't_2m:C' para temperatura), y coordenadas (latitud,longitud).",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "datetime": types.Schema(
                                type=types.Type.STRING,
                                description="Fecha y hora en formato ISO 8601 (ej: '2024-01-15T12:00:00Z'). Para rangos usar formato YYYY-MM-DDTHH:MM:SSZ--YYYY-MM-DDTHH:MM:SSZ:PT1H",
                            ),
                            "parameters": types.Schema(
                                type=types.Type.STRING,
                                description="Parámetros meteorológicos separados por comas (ej: 't_2m:C,precip_1h:mm,wind_speed_10m:ms')",
                            ),
                            "coordinates": types.Schema(
                                type=types.Type.STRING,
                                description="Coordenadas en formato 'latitud,longitud' (ej: '47.3667,8.5500')",
                            )
                        },
                        required=["datetime", "parameters", "coordinates"]
                    )
                ),
                types.FunctionDeclaration(
                    name="get_coordinates_from_address",
                    description="Usa esta función para convertir una dirección o nombre de lugar (como 'Ciudad de México' o 'Torre Eiffel') en coordenadas geográficas (latitud y longitud).",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "address": types.Schema(
                                type=types.Type.STRING,
                                description="La dirección, ciudad o nombre del lugar a convertir en coordenadas. Por ejemplo: 'París, Francia'",
                            )
                        },
                        required=["address"]
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
        if function_name == "get_coordinates_from_address":
            api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
            if not api_key:
                return {"success": False, "error": "API Key de Google Maps no configurada."}

            try:
                gmaps = googlemaps.Client(key=api_key)
                address = args.get("address")

                geocode_result = gmaps.geocode(address)

                if not geocode_result:
                    return {"success": False, "error": f"No se encontraron coordenadas para '{address}'. Pide al usuario que sea más específico."}

                location = geocode_result[0]['geometry']['location']
                lat = location['lat']
                lng = location['lng']

                return {"success": True, "location": f"{lat},{lng}"}

            except Exception as e:
                return {"success": False, "error": f"Error al llamar a la API de Geocoding: {str(e)}"}


        if function_name == "get_weather_data":
            username = os.environ.get("METEOMATICS_USERNAME")
            password = os.environ.get("METEOMATICS_PASSWORD")
            base_url = os.environ.get("METEOMATICS_API_URL", "https://api.meteomatics.com")

            if not username or not password:
                return {"success": False, "error": "Credenciales de Meteomatics no configuradas"}

            try:
                datetime_str = args.get("datetime")
                parameters = args.get("parameters")
                coordinates = args.get("coordinates")

                url = f"{base_url}/{datetime_str}/{parameters}/{coordinates}/json"

                response = requests.get(url, auth=(username, password), timeout=10)

                print(f"🌐 Llamada a Meteomatics: {url} - Código de estado: {response.status_code}")
                print(f"Respuesta: {response.text}")

                if response.status_code == 200:
                    return {"success": True, "data": response.json()}
                else:
                    return {"success": False, "error": f"API respondió con código {response.status_code}: {response.text}"}

            except Exception as e:
                return {"success": False, "error": f"Error al consultar Meteomatics: {str(e)}"}

        return {"success": False, "error": f"Función '{function_name}' no reconocida"}

    @classmethod
    def process_user_message(cls, conversation: Conversation, user_message: str) -> str:
        if not user_message or not user_message.strip():
            raise ValueError("El mensaje no puede estar vacío")

        try:
            client = cls._initialize_gemini()
            model_name = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

            history = cls.get_conversation_history(conversation)
            contents = []
            for msg in history:
                role = "user" if msg["role"] == "user" else "model"
                contents.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))

            cls.add_message(conversation, "user", user_message)
            contents.append(types.Content(role="user", parts=[types.Part(text=user_message)]))

            while True:
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=conversation.agent.system_prompt,
                        tools=cls.TOOLS,
                    ),
                )

                function_call = None
                for part in response.candidates[0].content.parts:
                    if part.function_call:
                        function_call = part.function_call
                        break

                if function_call:
                    function_name = function_call.name
                    function_args = dict(function_call.args)

                    print(f"🤖 Modelo solicita llamar a la función: {function_name} con args: {function_args}")

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
                else:
                    assistant_message = response.text
                    break

            cls.add_message(conversation, "assistant", assistant_message)
            return assistant_message

        except Exception as e:
            error_msg = f"Error al usar Google Gemini: {str(e)}"
            print(error_msg)
            raise Exception(error_msg)
