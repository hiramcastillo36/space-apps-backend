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
# SYSTEM PROMPT v2.1: skAI - Asistente Meteorológico Proactivo

## 1. 🎭 Personalidad y Misión
Eres **skAI**, un asistente meteorológico experto, proactivo y cortés. Tu misión principal es ofrecer una experiencia completa y útil al usuario, que consiste en tres acciones clave: **Extraer** la información necesaria, **Consultar** los datos del clima con precisión y, lo más importante, **Resumir** la información del clima y **Recomendar** acciones prácticas basadas en el pronóstico.

## 2. ⚙️ Flujo de Operación Obligatorio
Debes seguir estos pasos en orden para cada solicitud.

### **Paso 1: Análisis y Extracción Inicial**
Tu primera tarea es analizar la solicitud del usuario para extraer tres datos clave:
1.  **Tiempo:** Fecha y hora específicas (o rango).
2.  **Parámetros:** Las variables meteorológicas deseadas (ej. temperatura, viento).
3.  **Ubicación:** El lugar para el cual se necesita el pronóstico.

### **Paso 2: Completar Información Faltante (Usando Defaults)**
Si falta información, aplica estas reglas. **Solo haz una pregunta si es estrictamente necesario.**

* **UBICACIÓN (CRÍTICO):**
    * Si el usuario da un nombre de lugar (ej. "Ciudad de México" o "París"), **DEBES** usar la herramienta `get_coordinates_from_address` inmediatamente para obtener sus coordenadas. **Nunca pidas coordenadas numéricas.**
    * Si **NO** hay ubicación, tu única pregunta debe ser: *"¡Claro! ¿Para qué ciudad o lugar necesitas el pronóstico?"*

* **FECHA/TIEMPO (DEFAULT MEJORADO):**
    * Si no se especifica una fecha/hora, o si el usuario dice algo ambiguo como "hoy", "ahora", "mañana" o "en dos días", tu primer paso **OBLIGATORIO** es llamar a `get_current_datetime` para obtener la fecha y hora de inicio.
    * Luego, para la llamada a `get_weather_data`, **DEBES** construir un rango de pronóstico de 24 horas. Por ejemplo, si `get_current_datetime` devuelve '2025-10-05T15:00:00Z', el parámetro `datetime` para `get_weather_data` debe ser `'2025-10-05T15:00:00Z--2025-10-06T15:00:00Z:PT1H'`.
    * Si el usuario pide un pronóstico para una fecha específica pero sin hora (ej. "el clima para el 15 de enero"), asume la hora como las 12:00 PM de esa fecha.

* **PARÁMETROS (DEFAULT):**
    * Si no se especifican, asume por defecto los más comunes: `t_2m:C`, `wind_speed_10m:kmh`, `precip_1h:mm`, `prob_snowfall:p`.

### **Paso 3: Ejecución de Herramientas (Functions)**
Una vez que tengas la información completa, ejecuta las herramientas en este orden estricto:

1.  **`get_coordinates_from_address` (Si es necesario)**: Solo si tienes un nombre de lugar y no coordenadas.
2.  **`get_current_datetime` (Si es necesario)**: Solo si la fecha/hora es ambigua ("hoy", "ahora").
3.  **`get_weather_data`**: Llama a esta función con las coordenadas, el rango de fecha/hora y los parámetros correctos.
4.  **`save_event` (Condicional)**: **Si** el usuario mencionó un evento (fiesta, viaje, etc.), **DEBES** usar esta función después de obtener el clima. El parámetro `weather_data` debe ser un **string JSON válido con comillas dobles ("")**.

### **Paso 4: Construcción de la Respuesta Final (¡La Recomendación es Obligatoria!)**
**Toda** respuesta final al usuario, después de usar las herramientas, **DEBE** ser un resumen amigable y útil que **siempre incluya una recomendación**.

Tu respuesta debe contener:

1.  **Encabezado Claro:** Menciona la ubicación y la fecha/hora del pronóstico.
2.  **Resumen del Clima:** Interpreta los datos de la API en un lenguaje sencillo y natural (ej. "hará un día cálido", "viento ligero", "no se esperan lluvias").
3.  **Recomendación Práctica (SIEMPRE INCLUIR):** Esta es la parte más importante.
    * **Si hay un evento/actividad:** Da consejos específicos para el evento.
        * *Fiesta al aire libre:* "Es un gran día para tu fiesta, pero considera tener una carpa por si el viento levanta."
    * **Si no hay evento/actividad:** Ofrece consejos generales y útiles para el día.
        * *"Será una tarde soleada, ¡perfecta para salir a caminar! No olvides usar protector solar."*
        * *"Refrescará por la noche, así que te recomiendo llevar una chaqueta si vas a salir."*

**Ejemplo de respuesta ideal:**
*"¡Listo! Aquí tienes el pronóstico para Querétaro para mañana a las 3 PM. Se espera un día soleado y cálido con 25°C, vientos suaves y sin probabilidad de lluvia. ¡El clima es perfecto para tu parrillada! 🥩☀️ Te sugiero preparar bebidas refrescantes y tener un lugar con sombra para tus invitados. ¡Que la disfrutes!"*

## 3. 📊 Parámetros Meteorológicos Válidos
**IMPORTANTE:** Solo puedes usar los siguientes parámetros de la API. No inventes ni uses otros.

* **Temperatura:** `t_2m:C`, `t_2m:F`, `t_max_2m_24h:C`, `t_min_2m_24h:C`
* **Precipitación:** `precip_1h:mm`, `precip_24h:mm`, `prob_precip_1h:p`
* **Nieve:** `prob_snowfall:p`
* **Viento:** `wind_speed_10m:ms`, `wind_speed_10m:kmh`, `wind_dir_10m:d`, `wind_gusts_10m_1h:ms`
* **Otros:** `cloud_cover:p`, `visibility:m`, `relative_humidity_2m:p`, `msl_pressure:hPa`, `uv:idx`

**NOTA IMPORTANTE:** NO uses parámetros como `snow_depth:cm`, `fresh_snow_1h:cm`, `frost_depth:cm`, `soil_frost:p`, o `dew_point_2m:C` ya que NO están disponibles en el modelo mix de la API.

## 4. 🗣️ Tono y Estilo de Comunicación
Mantén siempre un tono natural, amigable, positivo y servicial. Haz que la interacción se sienta fácil y agradable.
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
                                description="Parámetros meteorológicos separados por comas (ej: 't_2m:C,precip_1h:mm,wind_speed_10m:ms,snow_depth:cm').",
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
                    name="get_current_datetime",
                    description="Obtiene la fecha y hora actuales en formato ISO 8601 (YYYY-MM-DDTHH:MM:SSZ). Útil para solicitudes de clima 'actual' o 'hoy'.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={}
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
    def get_current_datetime(cls) -> str:
        """Obtiene la fecha y hora actuales en formato ISO 8601"""
        print("Obteniendo fecha y hora actuales...")
        return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    @classmethod
    def _determine_mood(cls, assistant_message: str, weather_data: Dict = None) -> str:
        """
        Determina el mood/estado para iluminar la interfaz basado en la respuesta y datos meteorológicos
        Returns: 'sunny', 'cloudy', 'rainy', 'stormy', 'cold', 'hot', 'snow', 'neutral', 'success', 'loading'
        """
        message_lower = assistant_message.lower()

        # Extraer datos meteorológicos si están disponibles
        temperature = None
        precipitation = None
        wind_speed = None
        prob_snowfall = None
        snow_depth = None

        if weather_data and isinstance(weather_data, dict) and "data" in weather_data:
            for param in weather_data["data"]:
                if isinstance(param, dict):
                    param_name = param.get("parameter", "")
                    coords = param.get("coordinates", [])
                    if coords and isinstance(coords, list) and len(coords) > 0:
                        dates = coords[0].get("dates", [])
                        if dates and isinstance(dates, list) and len(dates) > 0:
                            value = dates[0].get("value")

                            if "t_2m:C" in param_name:
                                temperature = value
                            elif "precip" in param_name and "mm" in param_name:
                                precipitation = value
                            elif "wind_speed" in param_name:
                                wind_speed = value
                            elif "prob_snowfall" in param_name:
                                prob_snowfall = value
                            elif "snow_depth" in param_name:
                                snow_depth = value

        # Priorizar estados específicos basados en palabras clave
        if any(word in message_lower for word in ['guardado', 'evento guardado', 'registrado', '✅']):
            return 'success'
        elif any(word in message_lower for word in ['consultando', 'obteniendo', 'buscando', 'procesando']):
            return 'loading'

        # Detectar nieve
        # 1. Profundidad de nieve detectada
        if snow_depth is not None and snow_depth > 0:
            return 'snow'

        # 2. Alta probabilidad de nevada
        if prob_snowfall is not None and prob_snowfall > 50:
            return 'snow'

        # 3. Temperatura bajo cero + precipitación = nieve
        if temperature is not None and precipitation is not None:
            if temperature <= 0 and precipitation > 0.2:
                return 'snow'

        # 4. Temperatura muy baja + palabras clave de nieve (montañas, lugares fríos)
        if temperature is not None and temperature < -2:
            if any(word in message_lower for word in ['nieve', 'nevada', 'nevado', 'congelado', 'helado']):
                return 'snow'

        # Determinar mood basado en datos meteorológicos reales
        if precipitation is not None and precipitation > 5.0:
            # Lluvia fuerte
            if wind_speed and wind_speed > 40:
                return 'stormy'
            return 'rainy'

        if precipitation is not None and precipitation > 0.5:
            # Lluvia ligera o llovizna
            return 'rainy'

        if wind_speed is not None and wind_speed > 50:
            # Viento muy fuerte
            return 'stormy'

        if temperature is not None:
            # Temperatura extremadamente caliente (>35°C)
            if temperature > 35:
                return 'hot'
            # Temperatura agradable y sin precipitación = sunny
            elif temperature >= 18 and temperature <= 28 and (precipitation is None or precipitation < 0.5):
                return 'sunny'

        # Fallback a palabras clave del mensaje
        if any(word in message_lower for word in ['nieve', 'nevada', 'nevando', 'neva', 'granizo', '❄️', '⛄', 'snowfall']):
            return 'snow'
        elif any(word in message_lower for word in ['tormenta', 'vendaval', 'ráfagas', 'viento fuerte', '⛈️', 'peligro']):
            return 'stormy'
        elif any(word in message_lower for word in ['lluvia', 'llover', 'precipitación', 'mojado', '🌧️', 'paraguas']):
            return 'rainy'
        elif any(word in message_lower for word in ['soleado', 'despejado', 'perfecto', 'excelente', 'ideal', '☀️', 'sol']):
            return 'sunny'
        elif any(word in message_lower for word in ['nublado', 'nubes', 'cubierto', 'gris', '☁️']):
            return 'cloudy'
        elif any(word in message_lower for word in ['calor', 'caluroso', 'sofocante', 'muy caliente', '🔥']):
            return 'hot'
        elif any(word in message_lower for word in ['frío', 'helado', 'congelante', 'muy frío', 'glacial']):
            return 'cold'

        return 'neutral'

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
            prob_snowfall = None
            snow_depth = None

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
                                            elif "prob_snowfall" in param_name:
                                                prob_snowfall = value
                                            elif "snow_depth" in param_name:
                                                snow_depth = value

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
                wind_speed=wind_speed,
                prob_snowfall=prob_snowfall,
                snow_depth=snow_depth
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

        if function_name == "get_current_datetime":
            try:
                current_datetime = cls.get_current_datetime()
                return {"success": True, "current_datetime": current_datetime}
            except Exception as e:
                return {"success": False, "error": f"Error obteniendo fecha y hora actuales: {str(e)}"}

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
    def process_user_message(cls, conversation: Conversation, user_message: str) -> Dict:
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

            weather_data_from_api = None

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

                    # Guardar datos del clima si se obtuvieron
                    if function_name == "get_weather_data" and function_result.get("success"):
                        weather_data_from_api = function_result.get("data")

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

            # Determinar el mood para iluminar la interfaz
            mood = cls._determine_mood(assistant_message, weather_data_from_api)

            return {
                "message": assistant_message,
                "mood": mood
            }

        except Exception as e:
            error_msg = f"Error al usar Google Gemini: {str(e)}"
            print(error_msg)
            raise Exception(error_msg)
