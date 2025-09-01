import docker
import io
import tarfile
import requests

BASE_URL = "-131700382768.europe-west1.run.app"


def leerArchivo(filename, username, project):

    url = f"https://terminal-{username}-{project}{BASE_URL}/read-file"
    params = {"path": filename}
    response = requests.get(url, params=params)
    print(url)
    print(filename)

    if response.status_code == 200:
        data = response.json()
        print(params)
        print(response.url)
        print(data.get("content", ""))
        return data.get("content", "")
    else:
        raise Exception(f"Error al leer el archivo: {response.status_code}")
def guardarArchivo(ruta,texto,username,project):
    _, _, _, _, *direccion = ruta.split('/')
    direccion = '/'.join(direccion)
    url = f"https://terminal-{username}-{project}{BASE_URL}/write-file"
    payload = {"path": direccion, "content": texto}
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        data = response.json()
        return data.get("status", "Archivo guardado")
    else:
        raise Exception(f"Error al escribir el archivo: {response.status_code} - {response.text}")

 #Version antigua para archivos locales
"""
def leerArchivo(username, project, filename):
    file = "D:\\LocalFiles\\"+username+"\\" + project + "\\" +filename
    try:
        with open(file,'r',newline="") as archivo:
            contenido = archivo.read()

            return contenido
    except FileNotFoundError:
        return "Archivo no encontrado"
    except Exception as e:
        return "no se puede leer el archivo"


#leer archivos directamente dentro del contenedor
def leerArchivo(filename):
    client = docker.from_env()
    container = client.containers.get("terminal-container")

    exit_code, output = container.exec_run("cat /files/" + filename)

    if exit_code == 0:
        return output.decode()
    else:
        return "Error al leer el archivo"

#Version antigua para archivos locales

def guardarArchivo(ruta, texto):

    ruta = ruta.replace("/coding","")
    ruta = ruta.replace("/","\\")
    try:
        with open("D:\\LocalFiles" + "\\" + ruta, 'w', newline="") as archivo:
            archivo.write(texto)
            archivo.close()
            return True
    except Exception as e:
        return False


def guardarArchivo(ruta, texto):

    #La ruta que llega como parametro es la url de la plataforma. Primero la adaptamos para que sea similar a la ruta en el contenedor
    _, _,_,_, *direccion = ruta.split('/')
    ruta = "files/" + '/'.join(direccion)
    client = docker.from_env()
    container = client.containers.get("terminal-container")

    #abrimos el archivo e introducimos el texto actual con exec_run
    command = f"sh -c 'cat > {ruta}'"
    container.exec_run(command, stdin=True, socket=True).output.send(texto.encode("utf-8"))

    result = container.exec_run(f"cat {ruta}")
    print("Archivo guardado")
    return True
"""
def copiar_archivo_docker(archivo,nombre_archivo,ruta):
    client = docker.from_env()
    container = client.containers.get("python")

    tar_stream = io.BytesIO()
    with tarfile.open(fileobj=tar_stream, mode='w') as tar:
        tar.add(archivo, arcname=nombre_archivo)

    tar_stream.seek(0)
    container.put_archive(ruta,tar_stream)

    print("Archivo guardado en el contenedor")

    exit_code, output = container.exec_run(f"ls -l {ruta}")
    print(output.decode())
