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
        # ¡NUEVA LÓGICA AQUÍ!
        if function_name == "get_coordinates_from_address":
            api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
            if not api_key:
                return {"success": False, "error": "API Key de Google Maps no configurada."}

            try:
                gmaps = googlemaps.Client(key=api_key)
                address = args.get("address")

                # Llama a la API de Geocoding
                geocode_result = gmaps.geocode(address)

                if not geocode_result:
                    # Si no se encuentra el lugar, informa al modelo para que pueda preguntar de nuevo
                    return {"success": False, "error": f"No se encontraron coordenadas para '{address}'. Pide al usuario que sea más específico."}

                # Extrae la latitud y longitud del primer resultado
                location = geocode_result[0]['geometry']['location']
                lat = location['lat']
                lng = location['lng']

                # Devuelve el resultado en el formato que el modelo puede usar después
                return {"success": True, "location": f"{lat},{lng}"}

            except Exception as e:
                return {"success": False, "error": f"Error al llamar a la API de Geocoding: {str(e)}"}


        # Tu función existente para el clima espacial
        if function_name == "get_space_weather_data":
            # ... (tu código sin cambios)
            pass

        return {"success": False, "error": f"Función '{function_name}' no reconocida"}

    @classmethod
    def process_user_message(cls, conversation: Conversation, user_message: str) -> str:
        if not user_message or not user_message.strip():
            raise ValueError("El mensaje no puede estar vacío")

        try:
            client = cls._initialize_gemini()
            # 💡 RECOMENDACIÓN FUERTE: Usa un modelo estable. Los modelos 'exp' (experimentales)
            # pueden tener comportamientos inesperados como este.
            model_name = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

            # 1. Cargar el historial existente
            history = cls.get_conversation_history(conversation)
            contents = []
            for msg in history:
                role = "user" if msg["role"] == "user" else "model"
                contents.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))

            # 2. Añadir el nuevo mensaje del usuario
            cls.add_message(conversation, "user", user_message)
            contents.append(types.Content(role="user", parts=[types.Part(text=user_message)]))

            # 3. Bucle para procesar llamadas a funciones
            while True:
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=conversation.agent.system_prompt,
                        tools=cls.TOOLS,
                    ),
                )

                # ✅ INICIO DE LA CORRECCIÓN CLAVE
                # Búsqueda robusta de la llamada a función en TODAS las partes de la respuesta.
                function_call = None
                for part in response.candidates[0].content.parts:
                    if part.function_call:
                        function_call = part.function_call
                        break  # Encontramos una, no necesitamos seguir buscando
                # ✅ FIN DE LA CORRECCIÓN CLAVE

                if function_call:
                    function_name = function_call.name
                    function_args = dict(function_call.args)

                    print(f"🤖 Modelo solicita llamar a la función: {function_name} con args: {function_args}")

                    function_result = cls._call_external_api(function_name, function_args)

                    # Añadimos la petición del modelo (que contenía la function_call)
                    # y el resultado de nuestra función al historial.
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
                    # El bucle continúa para enviar este nuevo contexto al modelo
                else:
                    # Si, después de revisar todas las partes, NO hay llamada a función,
                    # entonces es seguro asumir que la respuesta es texto.
                    assistant_message = response.text
                    break  # Salimos del bucle

            # Guardamos la respuesta final del asistente en la base de datos
            cls.add_message(conversation, "assistant", assistant_message)
            return assistant_message

        except Exception as e:
            error_msg = f"Error al usar Google Gemini: {str(e)}"
            print(error_msg)
            raise Exception(error_msg)
