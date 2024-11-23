from django.urls import path
from .views import RegionStatisticsAPIView

urlpatterns = [
    path('region/<str:region_name>/', RegionStatisticsAPIView.as_view(), name='region_statistics'),
]
