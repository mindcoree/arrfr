from django.contrib import admin
from .models import TelegramUser

@admin.register(TelegramUser)
class TelegramUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'user_id', 'get_functions', 'quiz_points', 'last_activity')
    list_filter = ('last_activity',)
    search_fields = ('username', 'user_id')
    readonly_fields = ('last_activity', 'used_functions', 'quiz_points')
    ordering = ('-last_activity',)

    def get_functions(self, obj):
        return ", ".join(obj.used_functions) if obj.used_functions else "Нет использованных функций"
    get_functions.short_description = "Использованные функции"
