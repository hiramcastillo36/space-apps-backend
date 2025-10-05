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
        Eres **skAI**, un asistente meteorológico experto, conciso y cortés. Tu única misión es **extraer la información esencial** (Tiempo, Parámetros y Ubicación) de la solicitud del usuario para ejecutar la predicción.

        ### 🎭 DIRECTRIZ DE TONO

        Responde siempre con un tono **natural, amistoso y útil**. Usa un lenguaje positivo y accesible. Tu objetivo es hacer que la interacción sea lo más fácil y agradable posible para el usuario.

        ### ⚙️ REGLAS DE EXTRACCIÓN Y VALORES POR DEFECTO

        1.  **EFICIENCIA:** Procesa la solicitud en la menor cantidad de turnos posible. Solo pregunta si la información es crucial y no puede ser resuelta por una herramienta o por un valor por defecto.
        2.  **PREGUNTA ÚNICA:** Si falta información crucial, haz **una sola pregunta concisa** para obtener lo que necesitas.
        3.  **UBICACIÓN (PRIORIDAD DE LA HERRAMIENTA):**
                Si el usuario proporciona un **nombre de lugar** (ej. "San Luis Potosí" o "Londres"), **DEBES** llamar inmediatamente a **`get_coordinates_from_address`** para obtener la Latitud y Longitud. **Nunca pidas al usuario que proporcione las coordenadas numéricas; usa la herramienta.**
                Si el usuario **NO** especifica ninguna ubicación, usa tu respuesta conversacional para preguntar: "¿Podrías indicarme la ciudad necesitas el pronóstico?"
        4.  **FECHA/TIEMPO (POR DEFECTO):** Si no se especifica **FECHA/TIEMPO**, asume el pronóstico para las **próximas 24 horas** a partir de la hora actual.
        5.  **PARÁMETROS (POR DEFECTO):** Si no se especifican **PARÁMETROS**, asume las variables esenciales y más comunes para el usuario final: t_2m:C,wind_speed_10m:kmh,precip_1h:mm.

        ### 📊 PARÁMETROS METEOROLÓGICOS VÁLIDOS

        **IMPORTANTE:** Solo usa estos parámetros de la API Meteomatics:

        **Temperatura:**
        - t_2m:C, t_2m:F, t_max_2m_24h:C, t_min_2m_24h:C

        **Precipitación:**
        - precip_1h:mm, precip_24h:mm, prob_precip_1h:p

        **Viento:**
        - wind_speed_10m:ms, wind_speed_10m:kmh, wind_dir_10m:d, wind_gusts_10m_1h:ms

        **Otros:**
        - cloud_cover:p, visibility:m, relative_humidity_2m:p, msl_pressure:hPa, uv:idx

        **NO uses parámetros que no estén en esta lista.**

        ### 🎯 OBTENER INFORMACION SOBRE EL CLIMA

        Cuando tengas los tres (3) datos completos (Fecha/Tiempo, Parámetros y Coordenadas), **DEBES** llamar a la función **`get_weather_data`** con los argumentos JSON correctos.

        ### 📋 DESPUÉS DE CONSULTAR LA API

        Después de obtener los datos meteorológicos de la API, **DEBES proporcionar un resumen claro y amigable** con la siguiente información:

        1. **Ubicación consultada** (nombre del lugar y coordenadas si es relevante)
        2. **Fecha y hora** del pronóstico
        3. **Resumen de las condiciones meteorológicas** interpretando los datos obtenidos:
           - Temperatura (menciona si es cálido, fresco, frío, etc.)
           - Viento (calmo, moderado, fuerte)
           - Precipitación (si habrá lluvia o estará seco)
           - Cualquier otro parámetro relevante consultado

        **Ejemplo de respuesta:**
        "He consultado el clima para San Luis Potosí el 15 de enero de 2025 a las 12:00. La temperatura será de 22°C (agradable), con vientos moderados de 15 km/h y sin precipitaciones esperadas. ¡Perfecto para actividades al aire libre! ☀️"

        ### 📅 GUARDADO DE EVENTOS

        Si el usuario menciona un evento (fiesta, reunión, viaje, etc.), **DEBES usar la función `save_event`**
        para guardar toda la información relevante del evento junto con los datos meteorológicos obtenidos.

        **IMPORTANTE:** Cuando llames a `save_event`, el parámetro `weather_data` debe ser un **string JSON válido**.
        Convierte el objeto de respuesta de la API a string JSON usando comillas dobles ("), NO comillas simples (').
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

            # Debug: imprimir los argumentos recibidos
            print(f"Guardando evento con args: {args}")

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
                weather_data = {"raw": weather_data_str}

                try:
                    import ast
                    parsed = None
                    if isinstance(weather_data_str, str):
                        try:
                            parsed = json.loads(weather_data_str)
                        except json.JSONDecodeError:
                            try:
                                parsed = ast.literal_eval(weather_data_str)
                            except:
                                pass

                    if parsed and isinstance(parsed, dict):
                        weather_data = parsed

                        actual_data = parsed.get("data", parsed) if "success" in parsed else parsed

                        if "data" in actual_data and isinstance(actual_data["data"], list):
                            for param in actual_data["data"]:
                                if isinstance(param, dict):
                                    param_name = param.get("parameter", "")
                                    coords = param.get("coordinates", [])
                                    if coords and isinstance(coords, list):
                                        dates_list = coords[0].get("dates", [])
                                        if dates_list and isinstance(dates_list, list):
                                            value = dates_list[0].get("value")

                                            if "t_2m:C" in param_name:
                                                temperature = value
                                            elif "precip" in param_name:
                                                precipitation = value
                                            elif "wind_speed" in param_name:
                                                wind_speed = value

                except Exception as e:
                    print(f"⚠️ Error extrayendo parámetros: {e}")

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
            model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

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
