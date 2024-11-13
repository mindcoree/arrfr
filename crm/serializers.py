from rest_framework import serializers
from .models import TelegramUser

class TelegramUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = TelegramUser
        fields = [
            'user_id',
            'username',
            'full_name',
            'gender',
            'age',
            'region',
            'marital_status',
            'children',
            'benefits',
            'quiz_points',
            'used_functions',
            'last_activity',
            'is_registered',
            'is_web_user'
        ]