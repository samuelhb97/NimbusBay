import asyncio
import base64
import logging
import tempfile
import websockets

import docker
from channels.generic.websocket import AsyncWebsocketConsumer
import json
import threading
import re
import os

class DockerCommandConsumer(AsyncWebsocketConsumer):
    def __init__(self):
        super().__init__()
        self.docker_client = docker.from_env()
        self.container = None
        self.sock = None
        self.loop = asyncio.get_event_loop()
        self.reader_thread = None
        self.last_command = None

    #Nueva implementación para docker en cloud Run (api+websocket)

    async def connect(self):
        await self.accept()
        self.ws = await websockets.connect('ws://localhost:8002/ws')
        await asyncio.create_task(self.receive_from_container())

    async def receive_from_container(self):
        while True:
            data = await self.ws.recv()
            await self.send(text_data=data)

    async def receive(self, text_data):
        asyncio.run(self.ws.send(text_data))

    async def disconnect(self, code):
        if self.ws:
            await self.ws.close()

    #Antigua implementación para local (websocket con docker_exec)
"""
    async def connect(self):
        await self.accept()

        container_id = "python"  # Cambia esto al nombre del contenedor
        try:
            # Inicializar el contenedor de Docker
            self.container = self.docker_client.containers.get(container_id)
            _, self.sock = self.container.exec_run(
                cmd='bash', stdin=True, socket=True, tty=True
            )

            # Iniciar la tarea de lectura en segundo plano
            self.reader_thread = threading.Thread(target=self.read_output, daemon=True)
            self.reader_thread.start()

        except Exception as e:
            await self.send(text_data=json.dumps({"error": f"No se pudo conectar al contenedor: {e}"}))
            await self.close()

    async def disconnect(self, close_code):
        if self.sock:
            self.sock.close()

        if self.reader_thread and self.reader_thread.is_alive():
            self.reader_thread.join()

    async def receive(self, text_data):
        try:
            data = json.loads(text_data, strict=False)
            _type = data.get("type", "")

            if _type == "image":
                await self.send(text_data=json.dumps({"message": "imagen recibida"}))
                await self.send(text_data=json.dumps({
                    "type": "image",
                    "image": data["image"]
                }))


            command = data.get("command", "")

            if not command:
                #await self.send(text_data=json.dumps({"error": "No command provided"}))
                return

            if self.sock:
                 #if command.startswith("python"):
                    #await self.run_python_with_xvfb(command)
                   #else:
                self.last_command = command.strip()
                self.sock.sendall(bytes(command + '\n', 'utf-8'))
            else:
                await self.send(text_data=json.dumps({"error": "Shell is not open"}))

        except Exception as e:
            await self.send(text_data=json.dumps({"error": str(e)}))

    def read_output(self):
        #Lee la salida del contenedor y la envía al WebSocket en tiempo real
        buffer = ""
        while True:
            try:
                res = self.sock.recv(4096)
                if not res:
                    break  # Salir si no hay más datos

                # Decodificar y acumular en el buffer
                output = res.decode("utf-8")
                buffer += output

                # Procesar cada línea completa y enviarla al cliente
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    cleaned_line = self.clean_output(line + '\n')
                    if cleaned_line and cleaned_line != self.last_command:  # Ignorar líneas vacías después de limpiar
                        asyncio.run_coroutine_threadsafe(
                            self.send(text_data=json.dumps({"response": cleaned_line})),
                            self.loop,
                        )

                # Enviar cualquier contenido restante (incompleto) como es para manejo interactivo
                if buffer.strip() and buffer.strip() != self.last_command:
                    asyncio.run_coroutine_threadsafe(
                        self.send(text_data=json.dumps({"response": self.clean_output(buffer)})),
                        self.loop,
                    )

            except Exception as e:
                asyncio.run_coroutine_threadsafe(
                    self.send(text_data=json.dumps({"error": f"Error al leer: {e}"})),
                    self.loop,
                )
                break

    @staticmethod
    def clean_output(output):
        #Limpia la salida eliminando códigos de escape, prompts y caracteres de control.
        
        # Eliminar códigos de escape ANSI
        output = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', output)

        # Eliminar prompts del shell
        output = re.sub(r'root@[a-z0-9]+:.*# ', '', output)

        # Quitar líneas vacías adicionales y caracteres extraños
        return output.strip()

"""