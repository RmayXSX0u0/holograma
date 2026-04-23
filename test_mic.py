import speech_recognition as sr

print("Buscando micrófonos conectados...\n")
for indice, nombre in enumerate(sr.Microphone.list_microphone_names()):
    print(f"[{indice}] {nombre}")