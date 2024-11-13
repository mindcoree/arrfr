from django.db import models
from django.contrib.postgres.fields import ArrayField

# Create your models here.

class TelegramUser(models.Model):
    user_id = models.BigIntegerField(unique=True, verbose_name="ID пользователя")
    username = models.CharField(max_length=100, blank=True, null=True, verbose_name="Имя пользователя")
    last_activity = models.DateTimeField(auto_now=True, verbose_name="Последняя активность")
    used_functions = models.JSONField(default=list, verbose_name="Использованные функции")
    quiz_points = models.IntegerField(default=0, verbose_name="Очки за квиз")
    
    # Добавляем поля для анкетных данных
    full_name = models.CharField(max_length=255, blank=True, null=True, verbose_name="ФИО")
    gender = models.CharField(max_length=10, blank=True, null=True, verbose_name="Пол")
    age = models.IntegerField(blank=True, null=True, verbose_name="Возраст")
    region = models.CharField(max_length=100, blank=True, null=True, verbose_name="Регион")
    marital_status = models.CharField(max_length=50, blank=True, null=True, verbose_name="Семейное положение")
    children = models.CharField(max_length=50, blank=True, null=True, verbose_name="Количество детей")
    benefits = models.CharField(max_length=50, blank=True, null=True, verbose_name="Социальные пособия")
    is_registered = models.BooleanField(default=False, verbose_name="Зарегистрирован")
    is_web_user = models.BooleanField(default=False, verbose_name="Веб-пользователь")
    
    class Meta:
        verbose_name = "Пользователь Telegram"
        verbose_name_plural = "Пользователи Telegram"
        
    def __str__(self):
        return f"{self.username or 'Аноним'} ({self.user_id})"
