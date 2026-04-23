import speech_recognition as sr
import json
import time
import os
from gtts import gTTS
from pythonosc import udp_client

DIRECTORIO_ACTUAL = os.path.dirname(os.path.abspath(__file__))
CARPETA_AUDIOS = os.path.join(DIRECTORIO_ACTUAL, "audios_generados")

if not os.path.exists(CARPETA_AUDIOS):
    os.makedirs(CARPETA_AUDIOS)

IP_UNITY = "127.0.0.1"
PUERTO_UNITY = 5005
cliente_osc = udp_client.SimpleUDPClient(IP_UNITY, PUERTO_UNITY)

def guion(ruta_json): #carga guion
    ruta_completa_json = os.path.join(DIRECTORIO_ACTUAL, ruta_json)
    with open(ruta_json, "r", encoding="utf-8") as archivo:
        return json.load(archivo)

def voz(avatar, texto_respuesta):
    print(f"[{avatar.upper()}] generando voz para: '{texto_respuesta}'")
    nombre_limpio = avatar.replace("", "_")
    ruta_audio = os.path.join(CARPETA_AUDIOS, f"respuesta_{nombre_limpio}.mp3")
    #google TTS genera el audio
    tts = gTTS(text=texto_respuesta, lang='es', tld='com.mx')
    tts.save(ruta_audio)
    cliente_osc.send_message("/holograma/hablar", [avatar, ruta_audio]) # envia la orden a unity
    print(f"audio guardado en: {avatar.upper()}")

def escuchar_y_procesar(guion):
    r = sr.Recognizer()

    with sr.Microphone(device_index=1) as source: # device_index=1 es el puerto del microfono "19" es para un microfono externo
        print("ajustando sonido ")
        r.adjust_for_ambient_noise(source, duration=2)
        print("sistema listo")

        while True:
            try:
                #escucha constantemente con el timeout = none
                audio = r.listen(source, timeout=None, phrase_time_limit=5)
                #audio a google
                texto = r.recognize_google(audio, language="es-MX").lower()
                print(f"usuario dijo: '{texto}'")

                #buisqueda en guion
                for avatar, dialogos in guion.items():
                    #mencion del nombre del avatar
                    if avatar.lower() in texto:
                        #busca frase clave del guion
                        for frase_clave, texto_respuesta in dialogos.items():
                            if frase_clave.lower() in texto:
                                print(f"Coincide {avatar.upper()}")
                                voz(avatar, texto_respuesta)
                                time.sleep(3) # para que el micro no se escuche solo
                                break
                        break
            except sr.UnknownValueError:
                #si no entendio pasa desapercibido
                pass
            except sr.RequestError as e:
                print(f"Error de conexion con google: {e} revisa el internet")
            except Exception as e:
                print(f"error inesperado {e}")
            
if __name__ == "__main__":
    print("iniciando sistemas..")
    try:
        mi_guion = guion("guion.json")
        escuchar_y_procesar(mi_guion)
    except FileNotFoundError:
        print("no se encontro el archivo .json, crealo en la misma carpeta")


