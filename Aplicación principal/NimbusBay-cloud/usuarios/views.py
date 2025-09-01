from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib import messages
from .forms import RegistrationForm, LoginForm


def registro(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()  # Guardamos el nuevo usuario
            login(request, user)  # Iniciamos sesión automáticamente
            return redirect('home')  # Redirige a la página de inicio o donde quieras
    else:
        form = RegistrationForm()

    return render(request, 'usuarios/registro.html', {'form': form})

def login_custom(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, 'Nombre de usuario o contraseña incorrectos.')

    return render(request, 'usuarios/login.html')