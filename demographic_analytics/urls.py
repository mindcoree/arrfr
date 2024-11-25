from django.urls import path

from .views import (UserTrendsAnalyticsView,
                    UserActivityPredictionView,
                    RegionActivityAnalyticsAPIView,
                    BehavioralAnalyticsView,
                    RegionStatisticsAPIView

                    )

urlpatterns = [
    path('region/<str:region_name>/', RegionStatisticsAPIView.as_view(), name='region_statistics'),
    path('behavioral/', BehavioralAnalyticsView.as_view(), name='behavioral-analytics'),
    path('trends/', UserTrendsAnalyticsView.as_view(), name='user-trends'),
    path('predictions/', UserActivityPredictionView.as_view(), name='user-predictions'),
    path('activity/region/<str:region_name>/', RegionActivityAnalyticsAPIView.as_view(), name='region_activity_analytics'),
]


