import speech_recognition as sr
import json
import time
import os
from gtts import gTTS
import socket

DIRECTORIO_ACTUAL = os.path.dirname(os.path.abspath(__file__))
CARPETA_AUDIOS = os.path.join(DIRECTORIO_ACTUAL, "audios_generados")

if not os.path.exists(CARPETA_AUDIOS):
    os.makedirs(CARPETA_AUDIOS)

IP_UNITY = "127.0.0.1"
PUERTO_UNITY = 5005
cable_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

def guion(ruta_json): #carga guion
    ruta_completa_json = os.path.join(DIRECTORIO_ACTUAL, ruta_json)
    with open(ruta_json, "r", encoding="utf-8") as archivo:
        return json.load(archivo)

def voz(avatar, texto_respuesta, accion):
    ruta_audio= "NONE"
    if texto_respuesta.strip():
        print(f"[{avatar.upper()}] generando voz para: '{texto_respuesta}'")
        nombre_limpio = avatar.replace("", "_")
        ruta_audio = os.path.join(CARPETA_AUDIOS, f"respuesta_{nombre_limpio}.mp3")
        #google TTS genera el audio
        tts = gTTS(text=texto_respuesta, lang='es', tld='com.mx')
        tts.save(ruta_audio)
    else:
        print(f"[{avatar.upper()}] disparando accion")
    
    mensaje = f"{avatar}|{ruta_audio}|{accion}"
    cable_udp.sendto(mensaje.encode('utf-8'), ("127.0.0.1", 5005)) # envia la orden a unity
    print(f"mensaje enviado {accion}")

def escuchar_y_procesar(guion):
    r = sr.Recognizer()

    r.pause_threshold = 2.0 # 2 segundos antesde cortar la grabacion
    r.non_speaking_duration = 0.5
    with sr.Microphone(device_index=1) as source: # device_index=1 es el puerto del microfono "19" es para un microfono externo
        print("ajustando sonido ")
        r.adjust_for_ambient_noise(source, duration=2)
        print("sistema listo")

        while True:
            try:
                #escucha constantemente con el timeout = none
                audio = r.listen(source, timeout=None)
                #audio a google
                texto_crudo = r.recognize_google(audio, language="es-MX").lower()
                texto_limpio = texto_crudo.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
                print(f"usuario dijo: '{texto_crudo}' limpio: '{texto_limpio}'")

                if "apagate" in texto_limpio or "apaga el sistema" in texto_limpio:
                    print("apagando el sistema")
                    mensaje = "sistema|NONE|apagar_todo"
                    cable_udp.sendto(mensaje.encode('utf-8'), (IP_UNITY, PUERTO_UNITY))
                    break

                #buisqueda en guion
                for avatar, dialogos in guion.items():
                        #busca frase clave del guion
                        for frase_clave, datos in dialogos.items():
                            if avatar.lower() in texto_limpio and frase_clave.lower() in texto_limpio:
                                print(f"Coincide '{frase_clave}'")
                                voz(avatar, datos["texto"], datos["accion"])
                                time.sleep(4) # para que el micro no se escuche solo
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


