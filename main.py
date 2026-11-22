#!/usr/bin/env python3
"""
Teatro Holográfico Web (Todo-en-Uno):
  Micrófono (sounddevice) -> Whisper -> Guion JSON (con Fallback y Secuencias) -> Caché gTTS -> Pantalla Kiosco HTML5
"""
import argparse
import collections
import difflib
import http.server
import json
import os
import queue
import re
import shutil
import socketserver
import subprocess
import sys
import threading
import time
import webbrowser
from urllib.parse import unquote
from gtts import gTTS

if getattr(sys, 'frozen', False):
    DIRECTORIO_ACTUAL = os.path.dirname(sys.executable)
else:
    DIRECTORIO_ACTUAL = os.path.dirname(os.path.abspath(__file__))
CARPETA_AUDIOS = os.path.join(DIRECTORIO_ACTUAL, "audios_generados")
CARPETA_MEDIA = os.path.join(DIRECTORIO_ACTUAL, "multimedia")

os.makedirs(CARPETA_AUDIOS, exist_ok=True)
os.makedirs(CARPETA_MEDIA, exist_ok=True)

PUERTO_WEB = 8080
bloqueo_cooldown = False

# Estado global compartido con la pantalla web
ESTADO_TEATRO = {
    "id_orden": 0,
    "accion": "Idle",
    "archivo_media": "",
    "tipo_media": "none",
    "siguiente_media": "",   # URL del segundo video si es secuencia
    "siguiente_accion": "",
    "audio_url": "NONE",
    "loop": True,
    "apagar": False
}
LOCK_ESTADO = threading.Lock()


# ===========================================================================
# 1. INTERFAZ HOLOGRÁFICA HTML5 (CON SECUENCIA DE 2 CLIPS Y ANTI-BLOQUEO)
# ===========================================================================
HTML_HOLOGRAMA = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Teatro Holográfico</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body, html {
            width: 100vw; height: 100vh;
            background-color: #000000;
            overflow: hidden;
            display: flex; justify-content: center; align-items: center;
            font-family: sans-serif;
            cursor: none;
        }
        #escenario {
            position: relative;
            width: 100%; height: 100%;
            display: flex; justify-content: center; align-items: center;
        }
        video, img {
            max-width: 100%; max-height: 100%;
            object-fit: contain;
            transition: opacity 0.2s ease-in-out;
        }
        .oculto { opacity: 0; pointer-events: none; position: absolute; }
        .visible { opacity: 1; }
        #info-debug {
            position: fixed; top: 12px; left: 12px;
            color: #444; font-size: 13px; z-index: 50;
            pointer-events: none;
        }
    </style>
</head>
<body>
    <div id="info-debug">Iniciando sistema...</div>
    <div id="escenario">
        <video id="reproductor-video" class="oculto" playsinline></video>
        <img id="reproductor-imagen" class="oculto" src="" alt="" />
        <audio id="reproductor-audio"></audio>
    </div>

    <script>
        let ultimoIdOrden = -1;
        let urlSiguienteClip = "";
        let nombreSiguienteClip = "";

        const videoEl = document.getElementById('reproductor-video');
        const imgEl = document.getElementById('reproductor-imagen');
        const audioEl = document.getElementById('reproductor-audio');
        const debugEl = document.getElementById('info-debug');

        function mostrarMedia(tipo, url, loop, accionNombre) {
            if (tipo === 'video' && url) {
                imgEl.className = 'oculto';
                videoEl.className = 'visible';
                if (!videoEl.src.endsWith(encodeURI(url))) {
                    videoEl.src = url;
                }
                videoEl.loop = loop;
                videoEl.muted = false;
                videoEl.play().catch(e => {
                    videoEl.muted = true;
                    videoEl.play();
                });
                debugEl.innerText = "";
            } else if (tipo === 'imagen' && url) {
                videoEl.pause();
                videoEl.className = 'oculto';
                imgEl.src = url;
                imgEl.className = 'visible';
                debugEl.innerText = "";
            } else {
                debugEl.innerText = "[Estado: " + accionNombre + "] (Falta '" + accionNombre + ".mp4' en /multimedia)";
            }
        }

        // Cuando termina el audio MP3 de la voz, regresa a Idle y desbloquea micrófono
        audioEl.onended = () => {
            urlSiguienteClip = "";
            fetch('/volver_idle', { method: 'POST' });
        };

        // Parche anti-bloqueos si falla el dispositivo de audio
        audioEl.onerror = () => {
            urlSiguienteClip = "";
            fetch('/volver_idle', { method: 'POST' });
        };

        // Manejo de transición entre la animación 1 y la animación 2
        videoEl.onended = () => {
            if (!videoEl.loop) {
                if (urlSiguienteClip) {
                    const nextUrl = urlSiguienteClip;
                    const nextName = nombreSiguienteClip;
                    urlSiguienteClip = "";
                    // Reproducir la segunda animación en bucle mientras termina de hablar
                    mostrarMedia('video', nextUrl, true, nextName);
                } else if (audioEl.paused) {
                    fetch('/volver_idle', { method: 'POST' });
                }
            }
        };

        async function sincronizar() {
            try {
                const res = await fetch('/estado');
                const estado = await res.json();

                if (estado.apagar) {
                    window.close();
                    document.body.innerHTML = "";
                    return;
                }

                if (estado.id_orden !== ultimoIdOrden) {
                    ultimoIdOrden = estado.id_orden;
                    urlSiguienteClip = estado.siguiente_media || "";
                    nombreSiguienteClip = estado.siguiente_accion || "";

                    mostrarMedia(estado.tipo_media, estado.archivo_media, estado.loop, estado.accion);

                    if (estado.audio_url && estado.audio_url !== "NONE") {
                        audioEl.src = estado.audio_url + "?t=" + Date.now();
                        audioEl.play().catch(e => console.warn("Audio espera clic:", e));
                    } else {
                        audioEl.pause();
                    }
                }
            } catch (e) {}
            setTimeout(sincronizar, 150);
        }

        sincronizar();
    </script>
</body>
</html>
"""


# ===========================================================================
# 2. SERVIDOR WEB LOCAL Y CONTROL DE ESCENARIO
# ===========================================================================
def buscar_archivo_multimedia(accion):
    candidatos = [accion, accion.lower()]
    if accion.lower().startswith("animacion_"):
        sin_prefijo = accion[10:]
        candidatos.extend([sin_prefijo, sin_prefijo.lower()])

    for nombre in candidatos:
        for ext in [".mp4", ".webm", ".mov"]:
            ruta = os.path.join(CARPETA_MEDIA, nombre + ext)
            if os.path.exists(ruta):
                return f"/multimedia/{nombre}{ext}", "video"
        for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"]:
            ruta = os.path.join(CARPETA_MEDIA, nombre + ext)
            if os.path.exists(ruta):
                return f"/multimedia/{nombre}{ext}", "imagen"

    return "", "none"


def actualizar_escenario(accion, ruta_audio_local="NONE", loop=True):
    """Acepta una acción simple (str) o una secuencia de 2 acciones (list)."""
    global bloqueo_cooldown
    with LOCK_ESTADO:
        ESTADO_TEATRO["id_orden"] += 1
        if accion == "apagar_todo":
            ESTADO_TEATRO["apagar"] = True
            return

        # Detectar si es una lista de 2 animaciones (ej. ["animacion_saludar", "animacion_hablar"])
        if isinstance(accion, list) and len(accion) >= 2:
            accion_1, accion_2 = accion[0], accion[1]
            url_1, tipo_1 = buscar_archivo_multimedia(accion_1)
            url_2, tipo_2 = buscar_archivo_multimedia(accion_2)

            if tipo_1 == "none":
                url_1, tipo_1 = buscar_archivo_multimedia("Idle")
            if tipo_2 == "none":
                url_2, tipo_2 = buscar_archivo_multimedia("Idle")

            ESTADO_TEATRO["accion"] = accion_1
            ESTADO_TEATRO["archivo_media"] = url_1
            ESTADO_TEATRO["tipo_media"] = tipo_1
            ESTADO_TEATRO["loop"] = False  # El primer clip corre 1 vez para dar paso al segundo
            ESTADO_TEATRO["siguiente_media"] = url_2 if tipo_2 == "video" else ""
            ESTADO_TEATRO["siguiente_accion"] = accion_2
        else:
            accion_unica = accion[0] if isinstance(accion, list) else accion
            url_media, tipo_media = buscar_archivo_multimedia(accion_unica)
            if tipo_media == "none" and accion_unica != "Idle":
                url_idle, tipo_idle = buscar_archivo_multimedia("Idle")
                if tipo_idle != "none":
                    url_media, tipo_media = url_idle, tipo_idle

            ESTADO_TEATRO["accion"] = accion_unica
            ESTADO_TEATRO["archivo_media"] = url_media
            ESTADO_TEATRO["tipo_media"] = tipo_media
            ESTADO_TEATRO["loop"] = loop
            ESTADO_TEATRO["siguiente_media"] = ""
            ESTADO_TEATRO["siguiente_accion"] = ""

        if ruta_audio_local and ruta_audio_local != "NONE":
            nombre_mp3 = os.path.basename(ruta_audio_local)
            ESTADO_TEATRO["audio_url"] = f"/audios_generados/{nombre_mp3}"
            bloqueo_cooldown = True
        else:
            ESTADO_TEATRO["audio_url"] = "NONE"


class ManejadorHolograma(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORIO_ACTUAL, **kwargs)

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        ruta = unquote(self.path.split("?")[0])
        if ruta == "/" or ruta == "/index.html":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_HOLOGRAMA.encode("utf-8"))
        elif ruta == "/estado":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            with LOCK_ESTADO:
                self.wfile.write(json.dumps(ESTADO_TEATRO).encode("utf-8"))
        else:
            super().do_GET()

    def do_POST(self):
        global bloqueo_cooldown
        if self.path == "/volver_idle":
            bloqueo_cooldown = False
            actualizar_escenario("Idle", "NONE", loop=True)
            self.send_response(200)
            self.end_headers()


def iniciar_servidor_y_pantalla():
    socketserver.TCPServer.allow_reuse_address = True
    servidor = socketserver.ThreadingTCPServer(("127.0.0.1", PUERTO_WEB), ManejadorHolograma)
    hilo_srv = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo_srv.start()

    url = f"http://127.0.0.1:{PUERTO_WEB}"
    actualizar_escenario("Idle", "NONE", loop=True)

    rutas_navegadores = [
        shutil.which("chrome"),
        shutil.which("msedge"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for exe in rutas_navegadores:
        if exe and os.path.exists(exe):
            subprocess.Popen([
                exe,
                f"--app={url}",
                "--start-fullscreen",
                "--autoplay-policy=no-user-gesture-required"
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(" -> Pantalla Holográfica abierta en Modo Kiosco.")
            return

    webbrowser.open(url)


# ===========================================================================
# 3. GESTIÓN DE GUION Y CACHÉ DE AUDIOS (gTTS)
# ===========================================================================
def limpiar_nombre_archivo(texto):
    limpio = texto.replace(" ", "_")
    for c in ["?", "¿", "!", "¡", ":", "/", "\\", "*", "\"", "<", ">", "|", ",", "."]:
        limpio = limpio.replace(c, "")
    return limpio


def generar_audio_cache(texto, avatar, frase_clave):
    if not texto or not texto.strip():
        return "NONE"
    nombre_limpio = limpiar_nombre_archivo(avatar)
    frase_limpia = limpiar_nombre_archivo(frase_clave)
    ruta_audio = os.path.join(CARPETA_AUDIOS, f"respuesta_{nombre_limpio}_{frase_limpia}.mp3")

    if not os.path.exists(ruta_audio):
        print(f"Generando voz NUEVA para: '{frase_clave}'")
        tts = gTTS(text=texto, lang='es', tld='com.mx')
        tts.save(ruta_audio)

    return ruta_audio


def cargar_guion(ruta_json):
    ruta_completa = os.path.join(DIRECTORIO_ACTUAL, ruta_json)
    with open(ruta_completa, "r", encoding="utf-8") as archivo:
        return json.load(archivo)


def pre_renderizar_audios(guion_datos):
    print("[1/3] Verificando y pre-renderizando voces del guion en caché...")
    for avatar, dialogos in guion_datos.items():
        for frase_clave, datos in dialogos.items():
            texto = datos.get("texto", "")
            datos["ruta_audio"] = generar_audio_cache(texto, avatar, frase_clave)
    print("Todos los audios del guion están listos.")


# ===========================================================================
# 4. CEREBRO DEL GUION (CON FALLBACK) Y CAPTURA DE VOZ
# ===========================================================================
class CerebroGuion:
    def __init__(self, guion_datos):
        self.guion_datos = guion_datos

    @staticmethod
    def normalizar(texto):
        t = texto.lower()
        for k, v in {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u"}.items():
            t = t.replace(k, v)
        return re.sub(r"[^\w\s]", "", t).strip()

    @staticmethod
    def calcular_similitud(a, b):
        return difflib.SequenceMatcher(None, a, b).ratio()

    def procesar_entrada(self, entrada_cruda):
        texto_limpio = self.normalizar(entrada_cruda)
        if not texto_limpio:
            return None

        if ("apagate" in texto_limpio or "apaga el sistema" in texto_limpio or
                re.search(r"\b(adios|salir|terminar|parar|hasta luego|chao)\b", texto_limpio)):
            return ("sistema", "Apagando el sistema.", "NONE", "apagar_todo", False)

        mejor_match = None
        mayor_similitud = 0.0
        fallback_disponible = None

        for avatar, dialogos in self.guion_datos.items():
            for frase_clave, datos in dialogos.items():
                if frase_clave.lower() == "fallback":
                    fallback_disponible = (avatar, datos)
                    continue

                frase_limpia_dic = self.normalizar(frase_clave)
                similitud = self.calcular_similitud(texto_limpio, frase_limpia_dic)

                if frase_limpia_dic in texto_limpio or similitud > 0.6:
                    puntaje = 1.0 if frase_limpia_dic in texto_limpio else similitud
                    if puntaje > mayor_similitud:
                        mayor_similitud = puntaje
                        mejor_match = (avatar, frase_clave, datos, similitud)

        if mejor_match:
            avatar, frase_clave, datos, sim = mejor_match
            print(f"Match detectado! '{frase_clave}' (Similitud: {sim*100:.1f}%)")
            repetir = datos.get("loop", True)
            return (avatar, datos["texto"], datos["ruta_audio"], datos["accion"], repetir)

        # Si no hubo coincidencia pero existe 'fallback' en guion.json, lo usamos
        if fallback_disponible:
            avatar, datos = fallback_disponible
            print("Sin coincidencia exacta -> Activando respuesta de respaldo (fallback).")
            repetir = datos.get("loop", True)
            return (avatar, datos["texto"], datos["ruta_audio"], datos["accion"], repetir)

        return None


class Oidos:
    FRECUENCIA, BLOQUE = 16000, 480

    def __init__(self, device=None, silence_seconds=0.8, max_utterance_seconds=10):
        import sounddevice as sd
        self.q = queue.Queue()
        self.bloques_silencio = int(silence_seconds * self.FRECUENCIA / self.BLOQUE)
        self.bloques_maximos = int(max_utterance_seconds * self.FRECUENCIA / self.BLOQUE)
        self.stream = sd.InputStream(
            samplerate=self.FRECUENCIA, channels=1, dtype="float32",
            blocksize=self.BLOQUE, device=device,
            callback=lambda d, f, t, s: self.q.put(d[:, 0].copy())
        )
        self.stream.start()
        self.umbral = self._calibrar()

    def _calibrar(self):
        import numpy as np
        print("[3/3] Calibrando ruido de fondo (mantén silencio un momento)...")
        niveles = [np.sqrt(np.mean(self.q.get() ** 2)) for _ in range(int(self.FRECUENCIA / self.BLOQUE))]
        umbral = max(0.012, float(np.mean(niveles)) * 3)
        print(f"Umbral de voz detectado: {umbral:.4f}")
        return umbral

    def vaciar(self):
        with self.q.mutex:
            self.q.queue.clear()

    def escuchar(self):
        import numpy as np
        previo = collections.deque(maxlen=10)
        cuadros, silencioso, hablando = [], 0, False
        while True:
            bloque = self.q.get()
            fuerte = np.sqrt(np.mean(bloque ** 2)) > self.umbral
            if not hablando:
                previo.append(bloque)
                if fuerte:
                    hablando, cuadros, silencioso = True, list(previo), 0
                continue
            cuadros.append(bloque)
            silencioso = 0 if fuerte else silencioso + 1
            if silencioso >= self.bloques_silencio or len(cuadros) >= self.bloques_maximos:
                audio = np.concatenate(cuadros)
                if len(audio) > self.FRECUENCIA * 0.4:
                    return audio
                hablando = False


# ===========================================================================
# 5. CICLO PRINCIPAL
# ===========================================================================
def despachar_resultado(resultado):
    avatar, texto, ruta_audio, accion, repetir = resultado

    if accion == "apagar_todo":
        print("Apagando el sistema...")
        actualizar_escenario("apagar_todo")
        time.sleep(0.5)
        return False

    if texto.strip():
        print(f"[{avatar.upper()}] Dice: '{texto}'")
    else:
        print(f"[{avatar.upper()}] Disparando acción multimedia: {accion}")

    actualizar_escenario(accion, ruta_audio, loop=repetir)
    return True


def main():
    global bloqueo_cooldown
    ap = argparse.ArgumentParser()
    ap.add_argument("--guion", default="guion.json", help="Archivo JSON del guion")
    ap.add_argument("--text", action="store_true", help="Escribir consultas por teclado en vez de hablar")
    ap.add_argument("--list-mics", action="store_true", help="Listar micrófonos disponibles")
    ap.add_argument("--mic", type=int, default=None, help="Índice del micrófono")
    ap.add_argument("--model", default="base", help="Modelo de Whisper (tiny, base, small)")
    args = ap.parse_args()

    if args.list_mics:
        import sounddevice as sd
        print(sd.query_devices())
        return

    print("Iniciando Teatro Holográfico Web...")
    try:
        mi_guion = cargar_guion(args.guion)
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo '{args.guion}'.")
        return

    pre_renderizar_audios(mi_guion)
    cerebro = CerebroGuion(mi_guion)
    iniciar_servidor_y_pantalla()

    # --- MODO TEXTO ---
    if args.text:
        print("\n=== MODO TEXTO ACTIVO ===")
        print("Escribe una frase clave o cualquier pregunta para probar el fallback ('apagate' para salir):")
        while True:
            try:
                if not bloqueo_cooldown:
                    actualizar_escenario("animacion_escuchando", "NONE", loop=True)
                linea = input("\nTú > ")
            except (EOFError, KeyboardInterrupt):
                break

            actualizar_escenario("animacion_pensando", "NONE", loop=True)
            resultado = cerebro.procesar_entrada(linea)
            if resultado:
                if not despachar_resultado(resultado):
                    break
        return

    # --- MODO VOZ ---
    import whisper
    print(f"[2/3] Cargando modelo Whisper Offline ('{args.model}')...")
    modelo = whisper.load_model(args.model)
    oidos = Oidos(device=args.mic)

    oidos.vaciar()
    print("\nSistema listo. Escuchando... (di 'apágate' o 'salir' para terminar)")

    while True:
        try:
            if not bloqueo_cooldown:
                actualizar_escenario("animacion_escuchando", "NONE", loop=True)

            audio = oidos.escuchar()

            if bloqueo_cooldown:
                continue

            actualizar_escenario("animacion_pensando", "NONE", loop=True)

            t0 = time.time()
            res = modelo.transcribe(audio, language="es", fp16=False, condition_on_previous_text=False)
            texto_crudo = res["text"].strip()
            segs = res.get("segments", [])

            if not texto_crudo or (segs and max(s["no_speech_prob"] for s in segs) > 0.6):
                continue

            print(f"\nUsuario dijo: '{texto_crudo}' ({time.time() - t0:.1f}s en transcribir)")

            resultado = cerebro.procesar_entrada(texto_crudo)
            if resultado:
                if not despachar_resultado(resultado):
                    break
                # Esperar mientras termina de hablar con seguro anti-bloqueo de 35s
                tiempo_inicio = time.time()
                while bloqueo_cooldown and (time.time() - tiempo_inicio < 35):
                    time.sleep(0.2)
                bloqueo_cooldown = False
                oidos.vaciar()

        except KeyboardInterrupt:
            print("\nCerrando sistema...")
            break
        except Exception as e:
            print(f"Error inesperado: {e}")


if __name__ == "__main__":
    sys.exit(main())