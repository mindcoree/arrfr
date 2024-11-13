from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'users', views.TelegramUserViewSet)

urlpatterns = [
    path('', views.users_page, name='users_page'),
    path('api/', include(router.urls)),
    path('api/users-list/', views.users_list_api, name='users_list_api'),
    path('chat_with_gemini/', views.chat_with_gemini, name='chat_with_gemini'),
    path('api/get_user_data/', views.get_user_data, name='get_user_data'),
    path('api/export-excel/', views.export_users_excel, name='export_users_excel'),
]