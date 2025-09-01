import shutil
import tempfile
import time
import zipfile

import docker
import stat
from django.shortcuts import render, redirect
import os
import errno
from django.http import HttpResponse, HttpResponseForbidden
from django.conf import settings
from django.http import HttpResponseNotFound
from django.contrib.auth.decorators import login_required
from .forms import formulario
from .Scripts import leerArchivo, guardarArchivo
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from urllib.parse import parse_qs
from usuarios.models import Usuario, ProjectShare
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import io
from storages.backends.gcloud import GoogleCloudStorage
from google.oauth2 import service_account
from google.cloud import storage as gcs_native
from google.auth import default
from googleapiclient.discovery import build





def get_gcs_storage():
    credentials = service_account.Credentials.from_service_account_file(
        #archivo de credenciales de cuenta de servicio
        os.path.join(settings.BASE_DIR, "nimbusbay-9ac693c8142c.json")
    )
    return GoogleCloudStorage(bucket_name='nimbus-userstorage', credentials=credentials)


def get_native_gcs_client():
    credentials = service_account.Credentials.from_service_account_file(
        # archivo de credenciales de cuenta de servicio
        os.path.join(settings.BASE_DIR, "nimbusbay-9ac693c8142c.json")
    )
    return gcs_native.Client(credentials=credentials)

@csrf_exempt
def guardarArchivoVista(request):
    if request.method == "GET":
        texto = request.GET.get('texto')
        ruta = request.GET.get('ruta')
        username = request.GET.get('username')
        project = request.GET.get('project')
    elif request.method == "POST":
        data = parse_qs(request.body.decode())
        texto = data.get('texto', [''])[0]
        ruta = data.get('ruta', [''])[0]
        username = data.get('username', [''])[0]
        project = data.get('project', [''])[0]
    else:
        return JsonResponse({'mensaje': 'Método no permitido'}, status=405)

    res = guardarArchivo(ruta, texto, username, project)

    if res:
        return JsonResponse({'mensaje': 'Archivo guardado con éxito'})
    else:
        return JsonResponse({'mensaje': 'Ha ocurrido un error al guardar el archivo'})


@login_required
def codigo(request, username, project, params):
    if request.user.username != username:
        return HttpResponseForbidden("No tienes permiso para ver esta página.")

    texto_consola = ""
    textoRes = ""
    time.sleep(0.5)
    if request.method == 'POST':
        form = formulario(request.POST)
        if form.is_valid():
            action = request.POST.get('action')
            texto = form.cleaned_data['texto']
            guardarArchivo(params, texto, username, project)
            contenido_actual = leerArchivo(params,username,project)
            print('post, value:' + contenido_actual)
            form = formulario(initial={'texto': contenido_actual, 'texto_consola': texto_consola})
    else:
        contenido_actual = leerArchivo(params,username,project)
        print("params " +params)
        print('get, value:' + contenido_actual)
        form = formulario(initial={'texto': contenido_actual, 'texto_consola': ""})

    return render(request, 'coding/Code.html', {
        'form': form,
        'textoRes': textoRes,
        'username': username,
        'project': project,
        'params': params,
        'read_only': False
    })

@login_required
def lista(request, username):

    if request.user.username != username:
        return HttpResponseForbidden("No tienes permiso para ver esta página.")

    try:
        storage = get_gcs_storage()

        archivos = storage.listdir(username)[0]
        proyectos = archivos


        archivos_url = [
            {'nombre': proyecto, 'url': f'/coding/preparar_entorno/{username}/{proyecto}'}
            for proyecto in proyectos
        ]

        return render(request, 'coding/lista.html',{'archivos': archivos_url, 'username': username})
    except Exception as e:
        print("Error al listar archivos", e)
        return HttpResponseNotFound("No se pudo acceder al almacenamiento")
def cargar_archivo(request):
    response = leerArchivo(request.GET.get('path'),request.GET.get('username'),request.GET.get('project'))
    return HttpResponse(response, content_type='text/plain')

@login_required()
def vistaProyecto(request,username,project):
    if request.user.username != username:
        return HttpResponseForbidden("No tienes permiso para ver esta página.")
    contenido_inicial = "Bienvenido al editor de código, " + username + ".\nPara empezar a utilizar la herramienta seleccione un archivo en la barra lateral."
    form = formulario(initial={'texto': contenido_inicial, 'texto_consola': ""})
    return render(request, 'coding/Code.html', {
        'form': form,
        'username': username,
        'project': project,
        'read_only': True
    })


def preparar_entorno(request,username,project):
    return render(request, 'coding/preparar_entorno.html', {'username': username, 'project': project})


def esperar_exportacion(username, project, max_retries=10, delay=2):
    export_url = f"https://terminal-{username.lower()}-{project.lower()}-131700382768.europe-west1.run.app/actualizar-proyecto"
    for i in range(max_retries):
        response = requests.post(export_url)

        if response.status_code == 200:
            return True
        time.sleep(delay)
    return False
def crear_contenedor(request):
    username = request.GET.get('username')
    project = request.GET.get('project')
    if not username or not project:
        return JsonResponse({"status": "error", "message": "Faltan parámetros 'username' y/o 'project'"})

    service_name = f"terminal-{username}-{project}".lower()
    image_name = "gcr.io/nimbusbay/fastapi-terminal"
    project_name = "nimbusbay"
    location = "europe-west1"

    try:
        credentials, _ = default()
        run_service = build("run", "v1", credentials=credentials)

        parent = f"projects/{project_name}/locations/{location}"
        service_full_name= f"{parent}/services/{service_name}"


        service_body = {
            "apiVersion": "serving.knative.dev/v1",
            "kind": "Service",
            "metadata": {
                "name": service_name,
                "namespace": project_name
            },
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {
                            "autoscaling.knative.dev/minScale": "1",
                            "run.googleapis.com/timeoutSeconds": "3600"
                        }
                    },
                    "spec": {
                        "containers": [{
                            "image": image_name,
                            "env": [
                                {"name": "USERNAME", "value": username},
                                {"name": "PROJECT", "value": project},
                                {"name": "DJANGO_SERVICE_SECRET", "value": os.environ['DJANGO_SERVICE_SECRET']}
                            ],
                            "ports": [{"containerPort": 8080}],
                            "resources": {
                                "limits": {
                                    "memory": "1Gi"
                                }
                            }
                        }]
                    }
                }
            }
        }

        run_service.projects().locations().services().create(
            parent=parent,
            body=service_body
        ).execute()

        policy = run_service.projects().locations().services().getIamPolicy(
            resource=service_full_name
        ).execute()

        if "bindings" not in policy:
            policy["bindings"] = []

        policy["bindings"].append({
            "role": "roles/run.invoker",
            "members": ["allUsers"]
        })

        run_service.projects().locations().services().setIamPolicy(
            resource=service_full_name,
            body={"policy": policy}
        ).execute()

        return JsonResponse({
            "status": "ok",
            "message": "Contenedor desplegado correctamente",
            "container_name": service_name
        })
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)})

def check_container(request):

    username = request.GET.get("username")
    new_project = request.GET.get("project")
    if not username or not new_project:
        return JsonResponse({'error': 'Parámetros faltantes'}, status=400)

    try:

        credentials, _= default()
        run_service = build("run","v1", credentials=credentials)

        parent = f"projects/nimbusbay/locations/europe-west1"
        response = run_service.projects().locations().services().list(parent=parent).execute()
        print(response)
        services = response.get("items", [])
        print("servicios:")
        username_low = username.lower()
        found_project = None
        for svc in services:
            name = svc["metadata"]["name"]
            print(name)
            if name.startswith(f"terminal-{username_low}"):
                print("a")
                found_project = name.split(f"terminal-{username_low}-", 1)[1]
                break

        if not found_project:
            return JsonResponse({'exists': False})
        else:
            return JsonResponse({"exists": True, 'container_project': found_project})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def cerrar_contenedor(request):
    username = request.GET.get("username")
    container_project = request.GET.get("container_project")
    if not username or not container_project:
        return JsonResponse({'error': 'Parámetros faltantes'}, status=400)

    try:

        esperar_exportacion(username, container_project)

        service_name = f"terminal-{username}-{container_project}"
        full_service_path = f"projects/nimbusbay/locations/europe-west1/services/{service_name.lower()}"

        credentials, _= default()
        run_service = build("run", "v1", credentials=credentials)

        run_service.projects().locations().services().delete(
            name= full_service_path
        ).execute()

        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def handleRemoveReadonly(func, path, exc_info):
    excvalue = exc_info[1]
    if func in (os.rmdir, os.remove, os.unlink) and excvalue.errno == errno.EACCES:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    else:
        raise

def clear_tmp_directory(tmp_base):
    for item in os.listdir(tmp_base):
        item_path = os.path.join(tmp_base, item)
        try:
            if os.path.isfile(item_path) or os.path.islink(item_path):
                os.chmod(item_path, stat.S_IWRITE)
                os.remove(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path, onerror=handleRemoveReadonly)
        except Exception as e:
            print(f"No se pudo eliminar {item_path}: {e}")

@csrf_exempt
def inicializar_proyecto(request):
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed"}, status=405)

    username = request.POST.get("username")
    project = request.POST.get("project")

    if not username or not project:
        return JsonResponse({'error': 'Parámetros faltantes'}, status=400)
    try:
        max_size = 512*1024*1024
        project_zip_io = io.BytesIO()
        wheels_zip_io = io.BytesIO()

        if "project_zip" in request.FILES:
            uploaded_file = request.FILES["project_zip"]
            if uploaded_file.size > max_size:
                return JsonResponse({"error": "El archivo supera el límite permitido de 512 MB"}, status=400)

            for chunk in uploaded_file.chunks():
                project_zip_io.write(chunk)
        else:
            with zipfile.ZipFile(project_zip_io, "w") as zipf:
                pass

        with zipfile.ZipFile(wheels_zip_io,"w") as zipf:
            pass
        project_zip_io.seek(0)
        wheels_zip_io.seek(0)

        project_path = f"{username}/{project}/{project}.zip"
        wheels_path = f"{username}/{project}/{project}_wheels.zip"

        storage = get_gcs_storage()

        storage.save(project_path, ContentFile(project_zip_io.read()))
        storage.save(wheels_path,ContentFile(wheels_zip_io.read()))

        return JsonResponse({"success": True}, status=200)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def share_project(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method Not Allowed"}, status=405)

    sender = request.user
    recipient_username = request.POST.get("recipient")
    project = request.POST.get("project")

    if not recipient_username or not project:
        return JsonResponse({"error": "Datos incompletos"}, status=400)

    try:
        recipient = Usuario.objects.get(username=recipient_username)
    except Usuario.DoesNotExist:
        return JsonResponse({"error": "El usuairo destinatario no existe"}, status=404)

    share_request = ProjectShare.objects.create(
        sender = sender,
        recipient = recipient,
        project = project,
        status = 'pending'
    )
    return JsonResponse({"success": True, "message": "Solicitud enviada."}, status=200)

def mensajes(request):
    if not request.user.is_authenticated:
        return redirect('login')

    solicitudes = ProjectShare.objects.filter(recipient=request.user, status = 'pending')
    return render(request, "coding/mensajes.html", {"solicitudes": solicitudes})


def aceptar_share(request):
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)

    share_id = request.POST.get("share_id")
    response_value = request.POST.get("response")
    if not share_id:
        return JsonResponse({"error": "Falta share_id"}, status=400)

    try:
        share_request = ProjectShare.objects.get(id=share_id, recipient=request.user)
    except ProjectShare.DoesNotExist:
        return JsonResponse({"error": "Solicitud no encontrada"}, status=404)

    if response_value != "accepted":
        share_request.status = "rejected"
        share_request.save()
        return JsonResponse({"success": True, "message": "Solicitud rechazada."})

    # Si se acepta, actualizamos la solicitud y procedemos a copiar el proyecto.
    share_request.status = "accepted"
    share_request.save()
    sender_username = share_request.sender.username
    original_project = share_request.project
    shared_project = f"shared-{original_project}"

    storage = get_gcs_storage()

    try:
        source_zip_path = f"{sender_username}/{original_project}/{original_project}.zip"
        source_wheels_path = f"{sender_username}/{original_project}/{original_project}_wheels.zip"

        zip_bytes = storage.open(source_zip_path).read()
        wheels_bytes = storage.open(source_wheels_path).read()

        target_zip_path = f"{request.user.username}/{shared_project}/{shared_project}.zip"
        target_wheels_path = f"{request.user.username}/{shared_project}/{shared_project}_wheels.zip"

        storage.save(target_zip_path, ContentFile(zip_bytes))
        storage.save(target_wheels_path, ContentFile(wheels_bytes))

        return JsonResponse({"success": True, "message": "Proyecto importado correctamente"})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@login_required
def eliminar_proyecto(request, username, project):
    # Verificar que el usuario autenticado coincide con la URL
    if request.user.username != username:
        return JsonResponse({"error": "No tienes permiso para eliminar este proyecto."}, status=403)
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido."}, status=405)
    try:
        client = get_native_gcs_client()
        bucket = client.bucket('nimbus-userstorage')

        prefix = f"{username}/{project}/"
        blobs = bucket.list_blobs(prefix=prefix)

        archivos_eliminados=0
        for blob in blobs:
            blob.delete()
            archivos_eliminados +=1
        if archivos_eliminados == 0:
            return JsonResponse({"error": "Proyecto no encontrado."},status=404)

        return JsonResponse({"success":True,"message": f"Proyecto {project} eliminado correctamente."})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def close_run_service(request):
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)
    secret = request.headers.get("X-SERVICE-SECRET")
    if secret != os.environ["DJANGO_SERVICE_SECRET"]:
        return HttpResponseForbidden("Secreto inválido")

    data = request.POST or request.body
    service_name = data.get("service_name")
    if not service_name:
        return JsonResponse({"error": "Falta service_name"}, status=400)

    project = "nimbusbay"
    region="europe-west1"
    full_name = f"projects/{project}/locations/{region}/services/{service_name}"

    creds, _ = default()
    run_svc = build("run","v1",credentials=creds)
    try:
        run_svc.projects().locations().services().delete(name=full_name).execute()
        return JsonResponse({"success": True}, status=200)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)