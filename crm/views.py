from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
import google.generativeai as genai
from .models import TelegramUser
import json
import logging
import random
import string
from rest_framework import viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import TelegramUserSerializer
from openpyxl import Workbook
from datetime import datetime

# Настройка Gemini
genai.configure(api_key='AIzaSyC6gyL0t2vzDVNijIMbf1VL-igqPw-PsY4')
model = genai.GenerativeModel('gemini-pro')

REGISTRATION_STEPS = {
    'full_name': 'Пожалуйста, введите ваше ФИО',
    'gender': 'Укажите ваш пол (мужской/женский)',
    'age': 'Укажите ваш возраст',
    'region': 'В каком регионе вы проживаете?',
    'marital_status': 'Укажите ваше семейное положение',
    'children': 'Сколько у вас детей?',
    'benefits': 'Получаете ли вы социальные пособия? (да/нет)'
}

VALID_RESPONSES = {
    'gender': ['мужской', 'женский'],
    'marital_status': ['холост/не замужем', 'женат/замужем', 'в разводе', 'вдовец/вдова'],
    'benefits': ['да', 'нет']
}

def generate_user_id():
    return ''.join(random.choices(string.digits, k=10))

@csrf_exempt
def chat_with_gemini(request):
    if request.method == 'GET':
        return render(request, 'chat.html')
    
    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '')
            user_authorized = data.get('authorized', False)
            registration_step = data.get('registration_step', '')
            user_data = data.get('user_data', {})
            
            # Если пользователь не авторизован и нет текущего шага регистрации
            if not user_authorized and not registration_step:
                return JsonResponse({
                    'response': REGISTRATION_STEPS['full_name'],
                    'status': 'success',
                    'registration_started': True,
                    'registration_step': 'full_name'
                })
            
            # Обработка шагов регистрации
            if registration_step:
                # Валидация данных
                if registration_step == 'full_name':
                    names = user_message.strip().split()
                    if len(names) < 2:  # Изменили на 2 слова минимум
                        return JsonResponse({
                            'response': 'Пожалуйста, введите полное ФИО (минимум фамилия и имя)',
                            'status': 'error',
                            'registration_step': registration_step
                        })
                
                elif registration_step == 'gender':
                    if user_message.lower() not in VALID_RESPONSES['gender']:
                        return JsonResponse({
                            'response': 'Пожалуйста, выберите пол: мужской или женский',
                            'status': 'error',
                            'registration_step': registration_step
                        })
                
                elif registration_step == 'age':
                    try:
                        age = int(user_message)
                        if age < 18 or age > 100:
                            return JsonResponse({
                                'response': 'Пожалуйста, введите корректный возраст (от 18 до 100 лет)',
                                'status': 'error',
                                'registration_step': registration_step
                            })
                    except ValueError:
                        return JsonResponse({
                            'response': 'Пожалуйста, введите возраст числом',
                            'status': 'error',
                            'registration_step': registration_step
                        })
                
                elif registration_step == 'region':
                    if len(user_message.strip()) < 2:
                        return JsonResponse({
                            'response': 'Пожалуйста, введите корректное название региона',
                            'status': 'error',
                            'registration_step': registration_step
                        })
                
                elif registration_step == 'marital_status':
                    if user_message.lower() not in VALID_RESPONSES['marital_status']:
                        return JsonResponse({
                            'response': 'Пожалуйста, выберите один из вариантов семейного положения',
                            'status': 'error',
                            'registration_step': registration_step
                        })
                
                elif registration_step == 'children':
                    try:
                        children = int(user_message)
                        if children < 0 or children > 20:
                            return JsonResponse({
                                'response': 'Пожалуйста, введите корректное количество детей (от 0 до 20)',
                                'status': 'error',
                                'registration_step': registration_step
                            })
                    except ValueError:
                        return JsonResponse({
                            'response': 'Пожалуйста, введите количество детей числом',
                            'status': 'error',
                            'registration_step': registration_step
                        })
                
                elif registration_step == 'benefits':
                    if user_message.lower() not in VALID_RESPONSES['benefits']:
                        return JsonResponse({
                            'response': 'Пожалуйста, ответьте да или нет',
                            'status': 'error',
                            'registration_step': registration_step
                        })
                
                # Сохраняем введенные данные
                user_data[registration_step] = user_message
                
                # Определяем следующий шаг
                steps = list(REGISTRATION_STEPS.keys())
                current_index = steps.index(registration_step)
                
                if current_index < len(steps) - 1:
                    next_step = steps[current_index + 1]
                    return JsonResponse({
                        'response': REGISTRATION_STEPS[next_step],
                        'status': 'success',
                        'registration_step': next_step,
                        'user_data': user_data
                    })
                else:
                    # Регистрация завершена
                    user = TelegramUser.objects.create(
                        user_id=generate_user_id(),
                        username=user_data['full_name'].split()[1],
                        full_name=user_data['full_name'],
                        gender=user_data['gender'],
                        age=int(user_data['age']),
                        region=user_data['region'],
                        marital_status=user_data['marital_status'],
                        children=user_data['children'],
                        benefits=user_data['benefits'],
                        is_registered = True,
                        is_web_user = True
                    )
                    
                    # Формируем сообщение с данными пользователя
                    summary = f"""Регистрация успешно завершена! Ваши данные:
                    
ФИО: {user_data['full_name']}
Пол: {user_data['gender']}
Возраст: {user_data['age']}
Регион: {user_data['region']}
Семейное положение: {user_data['marital_status']}
Количество детей: {user_data['children']}
Социальные пособия: {user_data['benefits']}

Теперь вы можете задавать вопросы!"""
                    
                    return JsonResponse({
                        'response': summary,
                        'status': 'success',
                        'authorized': True,
                        'registration_complete': True,
                        'user_data': user_data
                    })
            
            # Если пользователь авторизован и регистрация завершена
            response = model.generate_content(user_message)
            return JsonResponse({
                'response': response.text,
                'status': 'success',
                'authorized': True
            })
            
        except Exception as e:
            return JsonResponse({
                'error': str(e),
                'status': 'error'
            }, status=500)

@csrf_exempt
def get_user_data(request):
    try:
        data = json.loads(request.body)
        search_query = data.get('query', '')
        
        if not search_query:
            return JsonResponse({
                'error': 'Поисковый запрос не может быть пустым',
                'status': 'error'
            }, status=400)
            
        # Поиск по user_id или ФИО
        try:
            if search_query.isdigit():
                user = TelegramUser.objects.get(user_id=search_query)
            else:
                user = TelegramUser.objects.get(full_name__icontains=search_query)
            
            return JsonResponse({
                'status': 'success',
                'data': {
                    'user_id': user.user_id,
                    'username': user.username,
                    'full_name': user.full_name,
                    'gender': user.gender,
                    'age': user.age,
                    'region': user.region,
                    'marital_status': user.marital_status,
                    'children': user.children,
                    'benefits': user.benefits,
                    'quiz_points': user.quiz_points,
                    'used_functions': user.used_functions,
                    'last_activity': user.last_activity.strftime("%Y-%m-%d %H:%M:%S")
                }
            })
            
        except TelegramUser.DoesNotExist:
            return JsonResponse({
                'error': 'Пользователь не найден',
                'status': 'error'
            }, status=404)
            
    except Exception as e:
        return JsonResponse({
            'error': str(e),
            'status': 'error'
        }, status=500)

class TelegramUserViewSet(viewsets.ModelViewSet):
    queryset = TelegramUser.objects.all().order_by('-last_activity')
    serializer_class = TelegramUserSerializer

def users_page(request):
    """Страница для отображения пользователей через API"""
    return render(request, 'crm/users.html')

@api_view(['GET'])
def users_list_api(request):
    """API endpoint для получения списка пользователей"""
    users = TelegramUser.objects.all().order_by('-last_activity')
    serializer = TelegramUserSerializer(users, many=True)
    return Response(serializer.data)

@api_view(['GET'])
def export_users_excel(request):
    """Экспорт пользователей в Excel"""
    users = TelegramUser.objects.all().order_by('-last_activity')
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Пользователи"
    
    # Заголовки
    headers = [
        'ID пользователя',
        'Имя пользователя',
        'ФИО',
        'Пол',
        'Возраст',
        'Регион',
        'Семейное положение',
        'Дети',
        'Соц. пособия',
        'Очки',
        'Использованные функции',
        'Статус регистрации',
        'Тип пользователя',
        'Последняя активность'
    ]
    
    ws.append(headers)
    
    # Данные
    for user in users:
        ws.append([
            user.user_id,
            user.username or '-',
            user.full_name or '-',
            user.gender or '-',
            user.age or '-',
            user.region or '-',
            user.marital_status or '-',
            user.children or '-',
            user.benefits or '-',
            user.quiz_points,
            ', '.join(user.used_functions) if user.used_functions else '-',
            'Да' if user.is_registered else 'Нет',
            'Веб' if user.is_web_user else 'Telegram',
            user.last_activity.strftime("%Y-%m-%d %H:%M:%S")
        ])
    
    # Автоматическая ширина колонок
    for column in ws.columns:
        max_length = 0
        column = list(column)
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = (max_length + 2)
        ws.column_dimensions[column[0].column_letter].width = adjusted_width
    
    # Создаем HTTP response
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename=users_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    
    wb.save(response)
    return response

