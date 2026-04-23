import speech_recognition as sr
import json
import time
import os

def guion(ruta_json):
    with open(ruta_json, "r", encoding="utf-8") as archivo:
        return json.load(archivo)

def reproducir(ruta_video): #reproductor
    print(f"Iniciando holograma: {ruta_video}")

    try: #abrir video
        os.startfile(ruta_video) #os.starfile en windows abre el reproductor predeterminado
    except AttributeError: #por si hay un error
        os.system(f"open {ruta_video}" if os.name == "posix" else f"xdg-open {ruta_video}")

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
                        for frase_clave, ruta_video in dialogos.items():
                            if frase_clave.lower() in texto:
                                print(f"Coincide {avatar.upper()}")
                                reproducir(ruta_video)

                                time.sleep(3) # para que el micro no se escuche solo
                                break
                        break
            except sr.UnknownValueError:
                #si no entendio pasa desapercibido
                pass
            except sr.RequestError as e:
                print(f"Error de conexion con google: {e} revisa el internet")
            except Exception as e:
                print("error inesperado {e}")
            
if __name__ == "__main__":
    print("iniciando sistemas..")
    try:
        mi_guion = guion("guion.json")
        escuchar_y_procesar(mi_guion)
    except FileNotFoundError:
        print("no se encontro el archivo .json, crealo en la misma carpeta")


