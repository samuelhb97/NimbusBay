from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.

class Usuario(AbstractUser):
    n_proyectos = models.IntegerField(null=True)

class ProjectShare(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pendiente'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    )
    sender = models.ForeignKey(Usuario, related_name='sent_shares', on_delete=models.CASCADE)
    recipient = models.ForeignKey(Usuario, related_name='received_shares', on_delete=models.CASCADE)
    project = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    def __str__(self):
        return f"{self.sender.username} comparte {self.project} con {self.recipient.username}"