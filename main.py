import speech_recognition as sr
import json
import time
import os
from gtts import gTTS
import socket
import glob
import threading
import difflib # Libreria nativa para logica matematica difusa

DIRECTORIO_ACTUAL = os.path.dirname(os.path.abspath(__file__))
CARPETA_AUDIOS = os.path.join(DIRECTORIO_ACTUAL, "audios_generados")

if not os.path.exists(CARPETA_AUDIOS):
    os.makedirs(CARPETA_AUDIOS)

IP_UNITY = "127.0.0.1"
PUERTO_UNITY = 5005
cable_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

bloqueo_cooldown = False

def limpiar_audios():
    print("[1/4] Limpiando audios generados anteriormente...")
    archivos = glob.glob(os.path.join(CARPETA_AUDIOS, "*.mp3"))
    for f in archivos:
        try:
            os.remove(f)
        except:
            pass
    print("Limpieza terminada.")

def guion(ruta_json):
    ruta_completa_json = os.path.join(DIRECTORIO_ACTUAL, ruta_json)
    with open(ruta_completa_json, "r", encoding="utf-8") as archivo:
        return json.load(archivo)

def pre_renderizar_audios(guion_datos):
    print("[2/4] Pre-renderizando voces...")
    for avatar, dialogos in guion_datos.items():
        for frase_clave, datos in dialogos.items():
            texto = datos["texto"]
            datos["ruta_audio"] = "NONE"
            
            if texto.strip():
                nombre_limpio = avatar.replace(" ", "_")
                frase_limpia = frase_clave.replace(" ", "_")
                ruta_audio = os.path.join(CARPETA_AUDIOS, f"respuesta_{nombre_limpio}_{frase_limpia}.mp3")
                
                print(f"Generando voz para: '{frase_clave}'")
                tts = gTTS(text=texto, lang='es', tld='com.mx')
                tts.save(ruta_audio)
                
                datos["ruta_audio"] = ruta_audio
    print("Todos los audios estan listos.")

def enviar_orden_unity(avatar, ruta_audio, accion):
    global bloqueo_cooldown
    mensaje = f"{avatar}|{ruta_audio}|{accion}"
    cable_udp.sendto(mensaje.encode('utf-8'), (IP_UNITY, PUERTO_UNITY))
    print(f"Mensaje enviado: {accion}")
    
    time.sleep(5) 
    bloqueo_cooldown = False

# NUEVA FUNCION: Calcula la similitud entre dos textos
def calcular_similitud(texto_usuario, frase_diccionario):
    # Retorna un valor flotante entre 0.0 y 1.0
    return difflib.SequenceMatcher(None, texto_usuario, frase_diccionario).ratio()

def escuchar_y_procesar(guion_datos):
    global bloqueo_cooldown
    r = sr.Recognizer()

    # Seguros de ruido para ignorar estatica
    r.energy_threshold = 500  
    r.dynamic_energy_threshold = False 
    r.pause_threshold = 2.0 
    r.non_speaking_duration = 0.5
    
    print("[3/4] Cargando modelo Whisper Offline...")
    
    with sr.Microphone(device_index=1) as source: 
        print("[4/4] Ajustando sonido...")
        r.adjust_for_ambient_noise(source, duration=2)
        print("Sistema listo. Escuchando...")

        while True:
            try:
                # Limite de frase a 7 segundos para no procesar audios gigantes
                audio = r.listen(source, timeout=None, phrase_time_limit=7)
                
                # Se cambio a modelo base para mayor precision
                texto_crudo = r.recognize_whisper(audio, model="base", language="es").lower()
                texto_limpio = texto_crudo.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u").replace("¿", "").replace("?", "").replace("¡", "").replace("!", "").replace(",", "").replace(".", "").strip()
                
                print(f"\nUsuario dijo: '{texto_crudo}' limpio: '{texto_limpio}'")

                if "apagate" in texto_limpio or "apaga el sistema" in texto_limpio:
                    print("Apagando el sistema...")
                    mensaje = "sistema|NONE|apagar_todo"
                    cable_udp.sendto(mensaje.encode('utf-8'), (IP_UNITY, PUERTO_UNITY))
                    break

                if not bloqueo_cooldown:
                    match_encontrado = False
                    for avatar, dialogos in guion_datos.items():
                        for frase_clave, datos in dialogos.items():
                            
                            # APLICANDO LOGICA DIFUSA
                            # Si el microfono fallo una letra, la similitud nos salvara
                            frase_limpia_diccionario = frase_clave.lower()
                            similitud = calcular_similitud(texto_limpio, frase_limpia_diccionario)
                            
                            # Aceptamos si la frase exacta esta dentro del texto, o si tiene al menos 80% de similitud
                            if frase_limpia_diccionario in texto_limpio or similitud > 0.6:
                                print(f"Match detectado! '{frase_clave}' (Similitud: {similitud*100:.1f}%)")
                                
                                if datos["texto"].strip():
                                    print(f"[{avatar.upper()}] Dice: '{datos['texto']}'")
                                else:
                                    print(f"[{avatar.upper()}] Disparando accion sin voz.")
                                
                                bloqueo_cooldown = True
                                
                                hilo = threading.Thread(target=enviar_orden_unity, args=(avatar, datos["ruta_audio"], datos["accion"]))
                                hilo.start()
                                
                                match_encontrado = True
                                break
                        if match_encontrado:
                            break
            except sr.UnknownValueError:
                pass
            except Exception as e:
                print(f"Error inesperado {e}")
            
if __name__ == "__main__":
    print("Iniciando sistemas...")
    try:
        limpiar_audios()
        mi_guion = guion("guion.json")
        pre_renderizar_audios(mi_guion)
        escuchar_y_procesar(mi_guion)
    except FileNotFoundError:
        print("No se encontro el archivo .json, crealo en la misma carpeta")