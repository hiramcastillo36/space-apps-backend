import os
import requests
from typing import Dict, List
from google import genai
from google.genai import types
from django.conf import settings
from .models import Agent, Conversation, Message, Event
import googlemaps
from datetime import datetime


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

        ### 📅 GUARDADO DE EVENTOS
        Si el usuario menciona un evento específico (fiesta, reunión, viaje, etc.), **DEBES usar la función `save_event`**
        para guardar toda la información relevante del evento junto con los datos meteorológicos obtenidos.
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
                ),
                types.FunctionDeclaration(
                    name="save_event",
                    description="Guarda un evento mencionado por el usuario con toda su información meteorológica relevante. Usa esta función cuando el usuario mencione una actividad o evento específico.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "event_name": types.Schema(
                                type=types.Type.STRING,
                                description="Nombre o descripción del evento (ej: 'Fiesta de cumpleaños', 'Reunión de trabajo', 'Viaje a la playa')",
                            ),
                            "event_date": types.Schema(
                                type=types.Type.STRING,
                                description="Fecha y hora del evento en formato ISO 8601 (ej: '2024-01-15T12:00:00Z')",
                            ),
                            "location_name": types.Schema(
                                type=types.Type.STRING,
                                description="Nombre del lugar del evento (ej: 'Ciudad de México', 'Playa del Carmen')",
                            ),
                            "latitude": types.Schema(
                                type=types.Type.NUMBER,
                                description="Latitud de la ubicación del evento",
                            ),
                            "longitude": types.Schema(
                                type=types.Type.NUMBER,
                                description="Longitud de la ubicación del evento",
                            ),
                            "weather_data": types.Schema(
                                type=types.Type.STRING,
                                description="Datos meteorológicos completos en formato JSON string obtenidos de la API",
                            )
                        },
                        required=["event_name", "event_date"]
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
    def _save_event(cls, conversation: Conversation, args: Dict) -> Dict:
        """Guarda un evento en la base de datos"""
        try:
            import json

            event_name = args.get("event_name")
            event_date_str = args.get("event_date")
            location_name = args.get("location_name", "")
            latitude = args.get("latitude")
            longitude = args.get("longitude")
            weather_data_str = args.get("weather_data")

            event_date = datetime.fromisoformat(event_date_str.replace('Z', '+00:00'))

            weather_data = None
            temperature = None
            precipitation = None
            wind_speed = None

            if weather_data_str:
                try:
                    weather_data = json.loads(weather_data_str) if isinstance(weather_data_str, str) else weather_data_str

                    if "data" in weather_data:
                        for param in weather_data["data"]:
                            param_name = param.get("parameter", "")
                            if "coordinates" in param and len(param["coordinates"]) > 0:
                                dates = param["coordinates"][0].get("dates", [])
                                if dates and len(dates) > 0:
                                    value = dates[0].get("value")

                                    if "t_2m:C" in param_name:
                                        temperature = value
                                    elif "precip" in param_name:
                                        precipitation = value
                                    elif "wind_speed" in param_name:
                                        wind_speed = value
                except json.JSONDecodeError:
                    pass

            event = Event.objects.create(
                user=conversation.user,
                conversation=conversation,
                event_name=event_name,
                event_date=event_date,
                location_name=location_name,
                latitude=latitude,
                longitude=longitude,
                weather_data=weather_data,
                temperature=temperature,
                precipitation=precipitation,
                wind_speed=wind_speed
            )

            return {
                "success": True,
                "message": f"Evento '{event_name}' guardado exitosamente",
                "event_id": event.id
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Error al guardar el evento: {str(e)}"
            }

    @classmethod
    def _call_external_api(cls, function_name: str, args: Dict, conversation: Conversation = None) -> Dict:
        if function_name == "save_event":
            if not conversation:
                return {"success": False, "error": "Conversación no disponible para guardar evento"}
            return cls._save_event(conversation, args)

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

                    function_result = cls._call_external_api(function_name, function_args, conversation)

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
