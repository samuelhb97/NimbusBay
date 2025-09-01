from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path("/ws/docker/", consumers.DockerCommandConsumer.as_asgi()),
]
