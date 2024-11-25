from rest_framework import serializers

class RegionStatisticsSerializer(serializers.Serializer):
    region = serializers.CharField()
    total_users = serializers.IntegerField()
    gender_distribution = serializers.DictField()
    age_distribution = serializers.DictField()
    marital_status = serializers.DictField()
    children_stats = serializers.DictField()
    benefits_stats = serializers.DictField()

from .models import UserAction

class UserActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAction
        fields = ['user', 'action_time', 'action_type', 'function_name']


class UserGrowthSerializer(serializers.Serializer):
    date = serializers.DateField()
    new_users = serializers.IntegerField()
    active_users = serializers.IntegerField()
    retention_rate = serializers.FloatField()