import json
from fastapi import FastAPI, WebSocket, Query, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from pathlib import Path
from pydantic import BaseModel
import zipfile
import requests
import re
import aiofiles
import base64
import os
import io
import pty
from PIL import Image, ImageChops
import tempfile
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from google.cloud import storage as gcs
import site

app = FastAPI()

BASE_LIBRARIES = {
    "aiofiles",
    "annotated-types",
    "anyio",
    "certifi",
    "charset-normalizer",
    "click",
    "fastapi",
    "h11",
    "httptools",
    "idna",
    "pillow",
    "pydantic",
    "pydantic_core",
    "python-dotenv",
    "PyYAML",
    "requests",
    "smmap",
    "sniffio",
    "starlette",
    "typing_extensions",
    "urllib3",
    "uvicorn",
    "uvloop",
    "watchfiles",
    "websockets",
    "google-cloud-storage"
}

active_terminal = None
active_master_fd = None

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://nimbusbay2.appspot.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],

)

BASE_WORKDIR = Path("/workdir")
SITE_PACKAGES_DIR = site.getsitepackages()[0]

last_mtime_project = 0
last_mtime_libs = 0

inactividad = 0
DJANGO_SECRET = os.environ.get("DJANGO_SERVICE_SECRET")
username = os.environ.get("USERNAME")
project = os.environ.get("PROJECT")

def imagen_vacia(im):
    extrema = im.getextrema()

    if isinstance(extrema, tuple) and isinstance(extrema[0], tuple):
        return all(channel[1] == 0 for channel in extrema)
    return extrema[1] == 0

def trim(im, border_color=(0,0,0)):

    if imagen_vacia(im):
        return im

    bg = Image.new(im.mode, im.size, border_color)
    diff = ImageChops.difference(im, bg)
    diff = ImageChops.add(diff, diff, 2.0, -100)
    bbox = diff.getbbox()
    if bbox:
        return im.crop(bbox)
    return im

@app.get("/")
async def read_root():
    return {"Hello": "World"}


@app.get("/read-file")
async def read_file(path: str = Query(..., description="Ruta del archivo")):
    reiniciar_inactividad()
    file_path = BASE_WORKDIR / path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    try:
        async with aiofiles.open(file_path, mode="r",encoding="utf-8") as f:
            content = await f.read()
        return {"content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error leyendo el archivo: {str(e)}")


class FileContent(BaseModel):
    path: str
    content: str


@app.post("/write-file")
async def write_file(file: FileContent):
    reiniciar_inactividad()
    file_path = BASE_WORKDIR / file.path
    try:
        async with aiofiles.open(file_path, mode="w", encoding="utf-8") as f:
            await f.write(file.content)
        return {"status": "Archivo actualizado"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error escribiendo el archivo: {str(e)}")

@app.post("/close-windows")
async def close_windows():
    reiniciar_inactividad()
    command = "wmctrl -c :ACTIVE:"

    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise HTTPException(status_code=500, detail=f"Error cerrando las ventanas: {stderr.decode().strip()}")

    return JSONResponse(content={"status": "Ventanas cerradas", "stdout": stdout.decode().strip()})

@app.get("/capture")
async def capture_screen():
    screenshot_path = "/tmp/screenshot.png"
    cmd = f"import -window root {screenshot_path}"

    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise HTTPException(status_code=500, detail=f"Error al capturar la pantalla: {stderr.decode()}")

    try:
        with Image.open(screenshot_path) as im:
            im_cropped = trim(im)
            buffered = io.BytesIO()
            im_cropped.save(buffered,format="PNG")
            image_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
            return JSONResponse(content={"image": image_base64})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error leyendo la captura: {str(e)}")


@app.get("/list-files")
async def list_files(username: str = Query(...), project: str = Query(...)):
    base_dir = "/workdir"
    if not os.path.exists(base_dir):
        raise HTTPException(status_code=404, detail="Directorio no encontrado")

    enlaces = {}
    for root, dirs, files in os.walk(base_dir):
        camino_relativo = os.path.relpath(root, base_dir)
        nivel_anidacion = camino_relativo.count(os.sep) if camino_relativo != '.' else 0
        nombre_directorio = os.path.basename(root)

        enlaces[camino_relativo] = {
            "nivel": nivel_anidacion,
            "directorio": nombre_directorio,
            "archivos": []
        }

        base_url = f"/coding/{username}/{project}/{camino_relativo}" if camino_relativo != '.' else f"/coding/{username}/{project}"
        for archivo in files:
            enlaces[camino_relativo]["archivos"].append({
                "nombre": archivo,
                "url": f"{base_url}/{archivo}"
            })

    return JSONResponse(content=enlaces)


@app.post("/importar-proyecto")
async def importar_proyecto(
        username: str = Query(...,description="Nombre de usuario"),
        project: str = Query(...,description="Nombre del proyecto")
):
    try:
        bucket_name = "nimbus-userstorage2"
        zip_path = f"{username}/{project}/{project}.zip"

        client = gcs.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(zip_path)

        if not blob.exists():
            raise HTTPException(status_code=404, detail="Archivo o proyecto no encontrado en GCS")

        zip_bytes = blob.download_as_bytes()

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zip_file:
            zip_file.extractall(BASE_WORKDIR)
        return JSONResponse(content={"mensaje": "Proyecto importado y extraido correctamente."})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"error importando el proyecto: {e}")


def filter_requirements(freeze_output: str) -> str:
    """
    Devuelve un string con las líneas de freeze_output que NO pertenezcan a BASE_LIBRARIES.
    """
    filtered = "\n".join(
        line for line in freeze_output.splitlines()
        if line and line.split("==")[0].strip() not in BASE_LIBRARIES
    )
    return filtered

def build_wheel(package: str, wheel_dir: str):
    """
    Ejecuta pip wheel para empaquetar la librería 'package' sin dependencias.
    """
    cmd = f"pip wheel --no-deps --only-binary=:all: --wheel-dir {wheel_dir} {package}"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return (package, result.returncode, result.stdout, result.stderr)

def build_wheels_concurrently(packages, wheel_dir, max_workers=4):
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(build_wheel, pkg, wheel_dir): pkg for pkg in packages}
        for future in futures:
            results.append(future.result())
    return results


async def exportar_proyecto():
    try:
        username = os.environ.get("USERNAME")
        project = os.environ.get("PROJECT")
        zip_base = os.path.join(tempfile.gettempdir(), f"{project}_export")
        zip_path = shutil.make_archive(zip_base, 'zip', root_dir="/workdir")

        export_temp = os.path.join(tempfile.gettempdir(), f"export_{username}_{project}")
        target_dir = os.path.join(export_temp, username, project)
        os.makedirs(target_dir, exist_ok=True)

        final_zip_path = os.path.join(target_dir, f"{project}.zip")
        shutil.move(zip_path, final_zip_path)

        bucket_name = "nimbus-userstorage2"
        client = gcs.Client()
        bucket = client.bucket(bucket_name)
        blob_zip = bucket.blob(f"{username}/{project}/{project}.zip")
        blob_zip.upload_from_filename(final_zip_path)

        shutil.rmtree(export_temp)

        return JSONResponse(content={"mensaje": "Proyecto exportado correctamente"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error exportando proyecto: {e}")


async def exportar_wheels():
    try:
        username = os.environ.get("USERNAME")
        project = os.environ.get("PROJECT")
        freeze_output = subprocess.check_output("pip freeze", shell=True, text=True)
        filtered_requirements = filter_requirements(freeze_output)
        requirements_file = os.path.join(tempfile.gettempdir(), "requirements.txt")
        with open(requirements_file, "w") as f:
            f.write(filtered_requirements)

        wheels_temp_dir = os.path.join(tempfile.gettempdir(), "wheels_dir")
        os.makedirs(wheels_temp_dir, exist_ok=True)

        packages = [line.split("==")[0].strip() for line in filtered_requirements.splitlines() if line.strip()]
        if packages:
            results = build_wheels_concurrently(packages, wheels_temp_dir)

        wheels_zip_base = os.path.join(tempfile.gettempdir(), f"{project}_wheels")
        wheels_zip_path = shutil.make_archive(wheels_zip_base, 'zip', root_dir=wheels_temp_dir)
        wheels_archive = os.path.join(tempfile.gettempdir(), f"{project}_wheels.zip")
        shutil.move(wheels_zip_path, wheels_archive)

        os.remove(requirements_file)
        shutil.rmtree(wheels_temp_dir)

        export_temp = os.path.join(tempfile.gettempdir(), f"export_{username}_{project}")
        target_dir = os.path.join(export_temp, username, project)
        os.makedirs(target_dir, exist_ok=True)

        final_wheels_path = os.path.join(target_dir, f"{project}_wheels.zip")
        shutil.copy(wheels_archive, final_wheels_path)

        bucket_name = "nimbus-userstorage2"
        client = gcs.Client()
        bucket = client.bucket(bucket_name)
        blob_wheels = bucket.blob(f"{username}/{project}/{project}_wheels.zip")
        blob_wheels.upload_from_filename(final_wheels_path)

        shutil.rmtree(export_temp)

        return JSONResponse(content={"mensaje": "Librerías exportadas correctamente."})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error exportando las librerías: {e}")


def obtener_mtime_recursivo(directorio):
    max_mtime = 0
    for root, dirs, files in os.walk(directorio):
        for file in files:
            filepath = os.path.join(root, file)
            try:
                mtime = os.path.getmtime(filepath)
                if mtime > max_mtime:
                    max_mtime = mtime
            except Exception as e:
                print(f"Error leyendo mtime de {filepath}: {e}")
    return max_mtime


@app.post("/actualizar-proyecto")
async def actualizar_proyecto():
    global last_mtime_project, last_mtime_libs
    #Se obtiene la última fecha de modificación de los directorios
    mtime_project = obtener_mtime_recursivo(BASE_WORKDIR)
    mtime_libs = obtener_mtime_recursivo(SITE_PACKAGES_DIR)

    mensajes = []
    if last_mtime_project == 0 and last_mtime_libs == 0:
        last_mtime_project = mtime_project
        last_mtime_libs = mtime_libs
    else:
        if mtime_project > last_mtime_project:
            await exportar_proyecto()
            last_mtime_project = mtime_project
            mensajes.append("Proyecto actualizado")

        if mtime_libs > last_mtime_libs:
            await exportar_wheels()
            last_mtime_libs = mtime_libs
            mensajes.append("Librerías actualizadas")

    if not mensajes:
        mensajes.append("No se han detectado cambios que actualizar")

    return JSONResponse(content={"mensaje": ", ".join(mensajes)})


async def tarea_periodica_actualizar():
    while True:
        try:
            await actualizar_proyecto()
        except Exception as e:
            print("Error actualizar_proyecto", e)
        await asyncio.sleep(60)


async def comprobar_inactividad():
    while True:
        global inactividad
        inactividad += 1
        if inactividad > 15:
            asyncio.create_task(notify_django_close())
        await asyncio.sleep(60)


def reiniciar_inactividad():
    global inactividad
    inactividad = 0


async def notify_django_close():
    url = "https://nimbusbay2.appspot.com/coding/close-service/"
    service_name = f"terminal-{username}-{project}".lower()
    headers = {"X-SERVICE-SECRET": DJANGO_SECRET}
    data = {"service_name": service_name}
    try:
        r = requests.post(url, data=data, headers=headers, timeout=5)
        r.raise_for_status()
    except Exception as e:
        print("Error notificando cierre a Django:", e)


@app.post("/install-wheels")
async def install_wheels(
        username: str = Query(..., description="Nombre del usuario"),
        project: str = Query(..., description="Nombre del proyecto")
):
    try:
        bucket_name = "nimbus-userstorage2"
        wheels_blob_path = f"{username}/{project}/{project}_wheels.zip"

        client = gcs.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(wheels_blob_path)

        if not blob.exists():
            raise HTTPException(status_code=404, detail="Archivo no encontrado en GCS")

        zip_bytes = blob.download_as_bytes()

        # Extraer el archivo zip en un directorio temporal
        extracted_dir = os.path.join(tempfile.gettempdir(), f"{project}_extracted_wheels")
        os.makedirs(extracted_dir, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as zip_ref:
            zip_ref.extractall(extracted_dir)
        print(f"Wheels extraídos en: {extracted_dir}")

        # Iterar sobre los archivos extraídos e instalar cada wheel
        installed = []
        for filename in os.listdir(extracted_dir):
            if filename.endswith(".whl"):
                wheel_file = os.path.join(extracted_dir, filename)
                result = subprocess.run(["pip", "install", wheel_file], capture_output=True, text=True)
                if result.returncode != 0:
                    raise Exception(f"Error instalando {filename}: {result.stderr}")
                installed.append(filename)
                print(f"Instalado: {filename}")

        # Limpiar el directorio temporal
        shutil.rmtree(extracted_dir)


        #inicializamos tarea periodica de actualización
        global last_mtime_project, last_mtime_libs
        last_mtime_project = obtener_mtime_recursivo(BASE_WORKDIR)
        last_mtime_libs = obtener_mtime_recursivo(SITE_PACKAGES_DIR)

        return JSONResponse(
            content={"mensaje": f"Librerías instaladas correctamente desde los wheels: {', '.join(installed)}."})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error instalando los wheels: {e}")

@app.on_event("startup")
async def iniciar_tarea():
    asyncio.create_task(tarea_periodica_actualizar())
    asyncio.create_task(comprobar_inactividad())
    print("Iniciando tarea")



@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global active_terminal, active_master_fd
    await websocket.accept()

    # Si ya hay un proceso activo, lo cerramos para evitar la
    # acumulación de procesos inactivos
    if active_terminal is not None:
        try:
            active_terminal.kill()
            os.close(active_master_fd)
            print("Se cerró la terminal anterior.")
        except Exception as e:
            print("Error cerrando terminal anterior:", e)
        active_terminal = None
        active_master_fd = None

    # Abrir un pseudo-TTY y guardar el master_fd globalmente
    master_fd, slave_fd = pty.openpty()
    active_master_fd = master_fd

    env = os.environ.copy()
    env["PS1"] = ""  # Sin prompt

    process = await asyncio.create_subprocess_exec(
        "bash", "-i",
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        cwd="/workdir",
        env=env
    )
    active_terminal = process

    os.close(slave_fd)
    os.write(master_fd, b"stty -echo\n")

    async def read_pty_output():
        loop = asyncio.get_running_loop()
        while True:
            data = await loop.run_in_executor(None, os.read, master_fd, 1024)
            if not data:
                break
            text = data.decode(errors="replace")
            lines = text.splitlines()
            filtered_lines = []
            for line in lines:
                # Filtra mensajes no deseados
                if ("cannot set terminal process group" in line or
                        "no job control in this shell" in line or
                        line.strip() == "stty -echo"):
                    continue
                if re.match(r".*@.*:/workdir\$$", line.strip()):
                    continue
                filtered_lines.append(line)



            if filtered_lines:
                await websocket.send_text("\n".join(filtered_lines))

    read_task = asyncio.create_task(read_pty_output())

    try:
        while True:
            data = await websocket.receive_text()
            reiniciar_inactividad()
            try:
                parsed = json.loads(data)
                command = parsed.get("command", "")
            except json.JSONDecodeError:
                command = data
            os.write(master_fd, command.encode() + b"\n")
    except Exception as e:
        print("Error en WebSocket:", e)
    finally:
        try:
            process.kill()
            os.close(master_fd)
        except Exception as ex:
            print("Error cerrando proceso:", ex)
        active_terminal = None
        active_master_fd = None
        await websocket.close()



if __name__ == "__main__":
    import os
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("api:app", host="0.0.0.0", port=port)
