from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.forms import AuthenticationForm
from .models import Usuario

class RegistrationForm(UserCreationForm):
    class Meta:
        model = Usuario
        fields = ['username', 'email']

class LoginForm(AuthenticationForm):
    username = forms.CharField(label='Usuario', widget=forms.TextInput(attrs={'class': 'form-control'}))
    password = forms.CharField(label='Password', widget=forms.PasswordInput(attrs={'class': 'form-control'}))
