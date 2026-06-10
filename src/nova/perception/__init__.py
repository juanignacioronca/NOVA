"""Percepción de NOVA: loop siempre-activo (audio + texto + video) que alimenta
el Estado del Mundo. Cada fuente es modular y **degradable**: si falta micrófono,
cámara o modelo, esa fuente se apaga con aviso y el resto sigue. Ver CLAUDE.md §3.

Todas las dependencias pesadas (sounddevice, opencv, faster-whisper, silero,
piper) se importan de forma **perezosa** dentro de los métodos, para que el
paquete importe (y los tests corran) sin tenerlas instaladas.
"""
