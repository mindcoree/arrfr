from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from crm.models import TelegramUser
from django.db.models import Avg, Count, IntegerField, Sum
from django.db.models.functions import Cast


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
