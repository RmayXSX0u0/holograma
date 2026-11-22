🎭 Teatro Holográfico Interactivo — UNACAR

Asistente virtual holográfico interactivo diseñado para proyectar un avatar institucional mediante la ilusión óptica de Pepper's Ghost sobre fondo negro puro (#000000). Desarrollado para la Universidad Autónoma del Carmen (UNACAR) por estudiantes de Ingeniería en Diseño Multimedia (Facultad de Ciencias de la Información).

El sistema opera bajo una arquitectura Web Local Monolítica (Todo-en-Uno) escrita en Python que integra captura de voz en tiempo real, reconocimiento automático del habla offline (Whisper), coincidencia semántica difusa, síntesis de voz con caché local (gTTS) y una interfaz gráfica HTML5/CSS3/JS en modo kiosco a pantalla completa.

📂 Estructura del Repositorio

TeatroHolografico/
│
├── main.py                  # Núcleo del sistema (Servidor HTTP, Voz, Whisper, TTS y Frontend HTML5 embebido)
├── guion.json               # Base de conocimiento institucional (preguntas, respuestas y secuencias visuales)
│
├── multimedia/              # Recursos visuales (.mp4, .webm, .png, .jpg) exportados sobre fondo #000000
│   ├── Idle.mp4
│   ├── animacion_escuchando.mp4
│   ├── animacion_pensando.mp4
│   ├── animacion_saludar.mp4
│   ├── animacion_hablar.mp4
│   ├── animacion_explicar.mp4
│   ├── animacion_emotiva.mp4
│   └── animacion_pensativa.mp4
│
└── audios_generados/        # Caché local de archivos de voz (.mp3) sintetizados automáticamente


⚙️ Arquitectura y Tecnologías

Python 3: Orquestación multihilo, control de estados (LOCK_ESTADO) y servidor web local sin dependencias externas pesadas.

Captura de Audio (sounddevice + NumPy): Registro continuo desde el micrófono a 16 kHz (bloques de 30 ms) con calibración automática de ruido ambiental y detección de actividad de voz (VAD) por energía RMS.

Reconocimiento de Voz Offline (OpenAI Whisper): Transcripción local en español con filtrado de falsos positivos (no_speech_prob > 0.6).

Motor Semántico (difflib + re): Normalización de texto y cálculo de similitud difusa (SequenceMatcher) contra guion.json, incluyendo respuesta de respaldo (fallback) para consultas fuera de libreto.

Síntesis de Voz con Caché (gTTS): Pre-renderizado de respuestas en archivos .mp3 almacenados en audios_generados/ para reproducción instantánea y ahorro de ancho de banda.

Interfaz Kiosco (HTML5 / CSS3 / JS + http.server): Servidor local en 127.0.0.1:8080 que lanza Chrome o Edge en modo aplicación sin bordes (--app, --start-fullscreen) y sincroniza estados mediante polling cada 150 ms.

🚀 Instalación y Requisitos

Clonar el repositorio:

git clone https://github.com/tu-usuario/tu-repositorio.git
cd tu-repositorio


Instalar las dependencias de Python:

pip install openai-whisper sounddevice numpy gTTS


(Nota: Asegúrate de tener instalado FFmpeg en tu sistema para que Whisper procese el audio correctamente).

Verificar recursos multimedia:
Coloca tus clips de video en formato .mp4 (renderizados sobre fondo negro puro) dentro de la carpeta multimedia/ respetando los nombres definidos en guion.json. Si falta algún clip específico, el sistema realizará un fallback automático hacia Idle.mp4.

💻 Uso y Ejecución

Modo Voz (Producción / Cabina Holográfica)

Inicia el calibrador de micrófono, levanta el servidor local y abre automáticamente la pantalla negra en modo kiosco:

python main.py


Modo Pruebas por Teclado (Depuración)

Permite escribir consultas directamente en la consola sin necesidad de utilizar el micrófono:

python main.py --text


Parámetros Adicionales

Listar dispositivos de entrada disponibles:

python main.py --list-mics


Seleccionar un micrófono específico por índice:

python main.py --mic 1


Cargar un archivo de guion alternativo o cambiar el modelo de Whisper (tiny, base, small):

python main.py --guion guion.json --model base


📝 Personalización de guion.json

El archivo guion.json permite configurar tanto animaciones individuales en bucle como secuencias encadenadas de 2 clips (donde el primero se reproduce una sola vez y el segundo continúa en bucle hasta finalizar la voz):

{
  "rectora": {
    "fallback": {
      "texto": "Disculpa, por el momento no cuento con esa información específica.",
      "accion": ["animacion_pensativa", "animacion_hablar"]
    },
    "mensaje nuevas generaciones": {
      "texto": "¡Bienvenidos a su casa! La UNACAR es un entorno donde sus aspiraciones encontrarán el impulso necesario.",
      "accion": ["animacion_saludar", "animacion_hablar"]
    },
    "oferta academica": {
      "texto": "Nuestra universidad ofrece una gama amplia de programas educativos distribuidos en tres campus.",
      "accion": "animacion_explicar"
    }
  }
}


📦 Compilación a Ejecutable (.exe)

Para generar un binario independiente en Windows mediante PyInstaller:

pip install pyinstaller
pyinstaller --noconfirm --onefile --console --name "TeatroHolografico" --collect-all whisper main.py


Al finalizar, copia guion.json, multimedia/ y audios_generados/ dentro de la carpeta dist/ junto a TeatroHolografico.exe.

👥 Créditos y Equipo de Desarrollo

Universidad Autónoma del Carmen (UNACAR)

Facultad de Ciencias de la Información — Ingeniería en Diseño Multimedia

Asesor: Prof. Benjamín Tass Herrera

May Barrera Roberto Gabriel
