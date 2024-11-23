from rest_framework import serializers

class RegionStatisticsSerializer(serializers.Serializer):
    region = serializers.CharField()
    total_users = serializers.IntegerField()
    gender_distribution = serializers.DictField()
    age_distribution = serializers.DictField()
    marital_status = serializers.DictField()
    children_stats = serializers.DictField()
    benefits_stats = serializers.DictField()
