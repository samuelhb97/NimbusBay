from django.urls import path

from . import views

urlpatterns = [
    path("", views.codigo, name="codigo"),
    path("cargar_archivo/", views.cargar_archivo,name="cargar_archivo"),
    path("lista/<str:username>", views.lista, name="lista"),
    path("guardar-archivo/", views.guardarArchivoVista, name="guardarArchivoVista"),
    path("preparar_entorno/<str:username>/<str:project>", views.preparar_entorno, name="preparar_entorno"),
    path("crear_contenedor", views.crear_contenedor, name="crear_contenedor"),
    path("check_container",views.check_container,name="check_container"),
    path("mensajes", views.mensajes, name="mensajes"),
    path("inicializar_proyecto",views.inicializar_proyecto, name="inicializar_proyecto"),
    path("aceptar_share", views.aceptar_share, name="aceptar_share"),
    path("cerrar_contenedor", views.cerrar_contenedor, name="cerrar_contenedor"),
    path("share_project", views.share_project, name="share_project"),
    path("close-service/", views.close_run_service, name="close_run_service"),
    path("eliminar_proyecto/<str:username>/<str:project>", views.eliminar_proyecto, name="eliminar_proyecto"),
    path("<str:username>/<str:project>", views.vistaProyecto, name="vistaProyecto"),
    path("<str:username>/<str:project>/<path:params>", views.codigo, name="codigo"),


]
