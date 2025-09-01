"""
ASGI config for djangoProject project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from coding.consumers import DockerCommandConsumer
from django.urls import path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'djangoProject.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),  # Manejo de solicitudes HTTP
    "websocket": AuthMiddlewareStack(  # Manejo de WebSockets con autenticación
        URLRouter([
            path("ws/docker/", DockerCommandConsumer.as_asgi()),  # Ruta WebSocket registrada
        ])
    ),
})
