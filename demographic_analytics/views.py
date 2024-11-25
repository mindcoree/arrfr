from crm.models import TelegramUser
from django.db.models.functions import Cast
from .models import UserAction
from django.db.models import Count
from django.contrib.auth.models import User
from .utils import predict_user_activity
from django.db.models.functions import TruncDate
import pandas as pd
from django.db.models import Min, Max, Avg, F, ExpressionWrapper, DurationField,IntegerField, Sum
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from datetime import timedelta, datetime
from django.utils.timezone import now


class RegionStatisticsAPIView(APIView):
    def get(self, request, region_name):
        # Фильтрация пользователей в регионе
        users = TelegramUser.objects.filter(region=region_name)

        if not users.exists():
            return Response({'error': 'Регион не найден'}, status=status.HTTP_404_NOT_FOUND)

        total_users = users.count()

        # Распределение по полу
        male_count = users.filter(gender__iexact="Мужской").count()
        female_count = users.filter(gender__iexact="Женский").count()
        male_percentage = (male_count / total_users * 100) if total_users > 0 else 0
        female_percentage = (female_count / total_users * 100) if total_users > 0 else 0

        # Возрастное распределение
        average_age = users.aggregate(Avg('age'))['age__avg'] or "Нет данных"
        age_groups = {
            "under_18": users.filter(age__lt=18).count(),
            "18_25": users.filter(age__gte=18, age__lte=25).count(),
            "26_40": users.filter(age__gte=26, age__lte=40).count(),
            "41_60": users.filter(age__gte=41, age__lte=60).count(),
            "61_100": users.filter(age__gte=61, age__lte=100).count(),
            "over_100": users.filter(age__gt=100).count()
        }

        # Валидные категории семейного положения
        valid_marital_statuses = ["Холост/Не замужем", "Женат/Замужем", "В разводе", "Вдовец/Вдова"]

        # Средний возраст в каждой группе семейного положения
        marital_status_avg_age = {
            (stat['marital_status'] if stat['marital_status'] in valid_marital_statuses else "Не указан"):
                users.filter(marital_status=stat['marital_status']).aggregate(avg_age=Avg('age'))[
                    'avg_age'] or "Не указан"
            for stat in users.values('marital_status').distinct()
        }

        # Распределение возраста по полу
        age_gender_distribution = {
            "male": {
                "under_18": users.filter(gender__iexact="Мужской", age__lt=18).count(),
                "18_25": users.filter(gender__iexact="Мужской", age__gte=18, age__lte=25).count(),
                "26_40": users.filter(gender__iexact="Мужской", age__gte=26, age__lte=40).count(),
                "41_60": users.filter(gender__iexact="Мужской", age__gte=41, age__lte=60).count(),
                "61_100": users.filter(gender__iexact="Мужской", age__gte=61, age__lte=100).count(),
                "over_100": users.filter(gender__iexact="Мужской", age__gt=100).count()
            },
            "female": {
                "under_18": users.filter(gender__iexact="Женский", age__lt=18).count(),
                "18_25": users.filter(gender__iexact="Женский", age__gte=18, age__lte=25).count(),
                "26_40": users.filter(gender__iexact="Женский", age__gte=26, age__lte=40).count(),
                "41_60": users.filter(gender__iexact="Женский", age__gte=41, age__lte=60).count(),
                "61_100": users.filter(gender__iexact="Женский", age__gte=61, age__lte=100).count(),
                "over_100": users.filter(gender__iexact="Женский", age__gt=100).count()
            }
        }


        # Распределение количества детей
        children_stats = {}
        for i in range(21):  # Категории от 0 до 20 детей
            children_stats[f"{i}_children"] = users.annotate(children_as_int=Cast('children', IntegerField())).filter(
                children_as_int=i).count()

        total_children = users.annotate(children_as_int=Cast('children', IntegerField())).aggregate(
            total=Sum('children_as_int')
        )['total'] or 0

        avg_children = users.annotate(children_as_int=Cast('children', IntegerField())).aggregate(
            avg=Avg('children_as_int')
        )['avg'] or 0


        # Социальные пособия
        benefits_stats = {
            "receiving_benefits": users.filter(benefits__iexact="Да").count(),
            "average_age_benefit_recipients": users.filter(benefits__iexact="Да").aggregate(Avg('age'))[
                                                  'age__avg'] or "Нет данных",
            "percentage_with_children": (users.filter(benefits__iexact="Да").exclude(
                children="0").count() / total_users * 100) if total_users > 0 else 0,
        }

        # Формирование итогового ответа
        data = {
            "region": region_name,
            "total_users": total_users,
            "gender_distribution": {
                "male_percentage": male_percentage,
                "female_percentage": female_percentage,
            },
            "age_distribution": {
                "average_age": average_age,
                "age_groups": age_groups,
                "age_gender_distribution": age_gender_distribution
            },
            "marital_status": {
                "distribution": marital_status_avg_age,
            },
            "children_stats": {
                "distribution": children_stats,
                "total_children": total_children,
                "average_children_per_user": avg_children,
            },
            "benefits_stats": benefits_stats,
        }

        return Response(data)


class BehavioralAnalyticsView(APIView):
    def get(self, request):
        # Частота активности
        daily_active_users = UserAction.objects.filter(
            action_time__gte=now() - timedelta(days=1)
        ).values('user').distinct().count()

        weekly_active_users = UserAction.objects.filter(
            action_time__gte=now() - timedelta(days=7)
        ).values('user').distinct().count()

        monthly_active_users = UserAction.objects.filter(
            action_time__gte=now() - timedelta(days=30)
        ).values('user').distinct().count()

        # Среднее количество действий
        daily_avg_actions = UserAction.objects.filter(
            action_time__gte=now() - timedelta(days=1)
        ).count() / daily_active_users if daily_active_users else 0

        # Последняя активность
        inactive_users = UserAction.objects.filter(
            action_time__lte=now() - timedelta(days=30)
        ).values('user').distinct().count()

        # Популярные функции
        top_functions = UserAction.objects.values('function_name').annotate(
            usage_count=Count('id')
        ).order_by('-usage_count')[:5]

        # Подготовка ответа
        data = {
            "daily_active_users": daily_active_users,
            "weekly_active_users": weekly_active_users,
            "monthly_active_users": monthly_active_users,
            "daily_avg_actions": daily_avg_actions,
            "inactive_users": inactive_users,
            "top_functions": list(top_functions),
        }
        return Response(data)

class UserTrendsAnalyticsView(APIView):
    def get(self, request):
        # Рост пользователей
        today = now().date()
        month_ago = today - timedelta(days=30)

        daily_new_users = User.objects.filter(date_joined__gte=today - timedelta(days=1)).count()
        monthly_new_users = User.objects.filter(date_joined__gte=month_ago).count()

        # Активные пользователи за месяц
        active_users = UserAction.objects.filter(
            action_time__gte=month_ago
        ).values('user').distinct().count()

        # Ретенция пользователей
        retention_data = []
        total_users = User.objects.all().count()
        if total_users > 0:
            retained_users = UserAction.objects.filter(
                action_time__gte=today - timedelta(days=30),
                action_time__lt=today
            ).values('user').distinct().count()
            retention_rate = (retained_users / total_users) * 100
        else:
            retention_rate = 0

        # Ответ данных
        data = {
            "daily_new_users": daily_new_users,
            "monthly_new_users": monthly_new_users,
            "monthly_active_users": active_users,
            "retention_rate": retention_rate,
        }
        return Response(data)

class UserActivityPredictionView(APIView):
    def get(self, request):
        # Используем TruncDate для извлечения даты
        user_activity = UserAction.objects.annotate(date=TruncDate('action_time')).values('date').annotate(activity_count=Count('id'))

        # Преобразуем QuerySet в DataFrame
        activity_df = pd.DataFrame(list(user_activity))

        # Проверяем, есть ли данные
        if activity_df.empty:
            return Response({"error": "Not enough data for prediction"}, status=400)

        # Прогноз
        predictions = predict_user_activity(activity_df)

        return Response({
            "predictions": predictions.tolist()
        })



class RegionActivityAnalyticsAPIView(APIView):
    def get(self, request, region_name=None):
        if region_name:
            # Фильтрация пользователей в указанном регионе
            users_in_region = TelegramUser.objects.filter(region=region_name)

            if not users_in_region.exists():
                return Response(
                    {"error": f"Регион '{region_name}' не найден или не содержит пользователей."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Общая статистика по региону
            total_users = users_in_region.count()

            # Средняя активность (по времени последней активности)
            avg_activity = users_in_region.annotate(
                activity_duration=ExpressionWrapper(
                    now() - F('last_activity'), output_field=DurationField()
                )
            ).aggregate(average_activity=Avg('activity_duration'))['average_activity']

            if avg_activity is not None:
                avg_activity_seconds = avg_activity.total_seconds()
                avg_activity_timedelta = timedelta(seconds=avg_activity_seconds)
                avg_activity_str = str(avg_activity_timedelta)
            else:
                avg_activity_str = None

            last_activity_stats = users_in_region.aggregate(
                earliest_activity=Min('last_activity'),
                latest_activity=Max('last_activity')
            )

            # Пользователи, зарегистрированные за последние 30 дней
            recent_users = users_in_region.filter(last_activity__gte=now() - timedelta(days=30)).count()

            # Формируем ответ для указанного региона
            response_data = {
                "region": region_name,
                "total_users": total_users,
                "last_activity": last_activity_stats,
                "recent_users": recent_users,
                "average_activity": avg_activity_str,
            }

            return Response(response_data, status=status.HTTP_200_OK)

        # Если регион не указан, собираем данные для всех регионов
        regions = TelegramUser.objects.values_list('region', flat=True).distinct()

        if not regions:
            return Response(
                {"error": "Нет доступных регионов для анализа."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Собираем данные для каждого региона
        region_activity_data = []
        for region in regions:
            users_in_region = TelegramUser.objects.filter(region=region)

            if users_in_region.exists():
                # Вычисляем среднюю активность
                avg_activity = users_in_region.annotate(
                    activity_duration=ExpressionWrapper(
                        now() - F('last_activity'), output_field=DurationField()
                    )
                ).aggregate(average_activity=Avg('activity_duration'))['average_activity']

                if avg_activity is not None:
                    avg_activity_seconds = avg_activity.total_seconds()
                    avg_activity_timedelta = timedelta(seconds=avg_activity_seconds)
                    avg_activity_str = str(avg_activity_timedelta)
                else:
                    avg_activity_str = None

                region_activity_data.append({
                    "region": region,
                    "total_users": users_in_region.count(),
                    "average_activity": avg_activity_str,
                })

        # Формируем общий ответ по всем регионам
        response_data = {
            "region_comparison": region_activity_data,
        }

        return Response(response_data, status=status.HTTP_200_OK)
