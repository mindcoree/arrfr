import os
import django

# Настройка Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fin_crm.settings")
django.setup()

import asyncio
import os
from aiogram import Bot, Dispatcher, types, Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
import openai
import logging
from crm.models import TelegramUser
from asgiref.sync import sync_to_async
from django.db.models import F
import aiohttp
from urllib.parse import urljoin

# Словарь эмодзи
QUIZ_EMOJIS = {
    'Финансы': '💰', 'Криптовалюты': '🪙', 'Инвестиции': '📈',
    'Стартапы': '🚀', 'Технологии': '💻', 'Кибербезопасность': '🔒',
    'Искусственный интеллект': '🤖', 'Маркетинг': '📊', 'Бизнес': '💼',
    'Образование': '📚'
}

# Инициализация
bot = Bot(token='TOKEN')
dp = Dispatcher()
router = Router()
openai.api_key = ''
logging.basicConfig(level=logging.INFO)
# ID группы, куда будут пересылаться сообщения
TARGET_GROUP_ID = '-1002397619653'

# Состояния FSM
class Form(StatesGroup):
    choosing_input_method = State()
    waiting_for_gender = State()
    waiting_for_age = State()
    waiting_for_region = State()
    waiting_for_marital_status = State()
    waiting_for_children = State()
    waiting_for_benefits = State()
    waiting_for_name = State()
    waiting_for_full_text = State()
    quiz_topic_selection = State()
    quiz_question = State()
    editing_field = State()
    waiting_for_user_search = State()

# Клавиатуры
gender_kb = ReplyKeyboardMarkup(
    keyboard=[  
        [KeyboardButton(text="Мужской"), KeyboardButton(text="Женский")]
    ],
    resize_keyboard=True
)

marital_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Холост/Не замужем"), KeyboardButton(text="Женат/Замужем")],
        [KeyboardButton(text="В разводе"), KeyboardButton(text="Вдовец/Вдова")]
    ],
    resize_keyboard=True
)

benefits_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Да"), KeyboardButton(text="Нет")]
    ],
    resize_keyboard=True
)

input_method_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Пошаговый ввод")],
        [KeyboardButton(text="Ввести всё сразу")]
    ],
    resize_keyboard=True
)

# Список городов Казахстана
KAZAKHSTAN_CITIES = [
    "Алматы", "Астана", "Шымкент", "Актобе", "Караганда", 
    "Тараз", "Павлодар", "Усть-Каменогорск", "Семей", 
    "Атырау", "Костанай", "Кызылорда", "Уральск", 
    "Петропавловск", "Актау", "Темиртау", "Туркестан", 
    "Кокшетау", "Талдыкорган", "Экибастуз"
]

# Клавиатура для городв
cities_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=city)] for city in KAZAKHSTAN_CITIES
    ],
    resize_keyboard=True
)

# Обновляем клавиатуру с функциями
functions_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Фиансы"), KeyboardButton(text="Криптовалюты"), KeyboardButton(text="Инвестиии")],
        [KeyboardButton(text="Стартапы"), KeyboardButton(text="Технологии"), KeyboardButton(text="Кибербезопасность")],
        [KeyboardButton(text="ИИ"), KeyboardButton(text="Маркетинг"), KeyboardButton(text="Бизнес")],
        [KeyboardButton(text="Образование"), KeyboardButton(text="Проверить себя"), KeyboardButton(text="Личный кабинет")],
        [KeyboardButton(text="🔍 Поиск пользователя")]
    ],
    resize_keyboard=True
)

# Клавиатура для личного кабинета
profile_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Изменить данные", callback_data="profile:edit")],
        [InlineKeyboardButton(text="Вернуться в меню", callback_data="profile:menu")]
    ]
)

# Клавиатура для выбора поля для изменения
edit_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="ФИО", callback_data="edit:full_name")],
        [InlineKeyboardButton(text="Возраст", callback_data="edit:age")],
        [InlineKeyboardButton(text="Регион", callback_data="edit:region")],
        [InlineKeyboardButton(text="Семейное положение", callback_data="edit:marital_status")],
        [InlineKeyboardButton(text="Количество детей", callback_data="edit:children")],
        [InlineKeyboardButton(text="Социальные пособия", callback_data="edit:benefits")],
        [InlineKeyboardButton(text="Назад", callback_data="edit:back")]
    ]
)

# Функция для сохранени запроса в БД
@sync_to_async
def save_user_request_sync(user_id: int, username: str, function_name: str):
    try:
        # Получаем или создаем запись пользователя
        user, created = TelegramUser.objects.get_or_create(
            user_id=user_id,
            defaults={'username': username, 'used_functions': []}
        )
        
        # Обновляем имя пользователя, если оно изменилось
        if user.username != username and username is not None:
            user.username = username
        
        # Получаем текущий список функций
        current_functions = user.used_functions if isinstance(user.used_functions, list) else []
        
        # Добавляем функцию в список, если её там ещё нет
        if function_name not in current_functions:
            current_functions.append(function_name)
            user.used_functions = current_functions
            user.save()
        
    except Exception as e:
        logging.error(f"Error saving user request: {e}")
        raise  # Добавляем raise для лучшего отслеживания ошибок

# Асинхронная обертка для сохранения запроса
async def save_user_request(user_id: int, username: str, function_name: str):
    await save_user_request_sync(user_id, username, function_name)

# Обработчик команды /start
@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    try:
        # Проверяем, существует ли пользователь и зарегистрирован ли он
        user = await sync_to_async(TelegramUser.objects.filter(user_id=message.from_user.id).first)()
        
        if user and user.is_registered:
            # Если пользователь уже зарегистрирован, показываем меню функций
            await message.reply(
                "Добро пожаловать назад! Выберите интересующую вас тему:",
                reply_markup=functions_kb
            )
        else:
            # Если пользователь е зарегистрирован, начинаем регистрацию
            if not user:
                # Создаем нового пользователя
                await sync_to_async(TelegramUser.objects.create)(
                    user_id=message.from_user.id,
                    username=message.from_user.username
                )
            
            await state.set_state(Form.choosing_input_method)
            await message.reply(
                "Здравствуйте! Для начала работы необходимо зарегистрироваться.\n"
                "Выберите способ ввода данных:",
                reply_markup=input_method_kb
            )
    except Exception as e:
        logging.error(f"Error in start command: {e}")
        await message.reply("Произошла ошибка. Пожалуйста, попробуйте позже.")

# Обработчик выбора метода ввода
@router.message(Form.choosing_input_method)
async def process_input_method(message: types.Message, state: FSMContext):
    if message.text == "Пошаговый ввод":
        await state.set_state(Form.waiting_for_name)
        await message.reply(
            "Введите ваше ФИО:",
            reply_markup=ReplyKeyboardRemove()
        )
    elif message.text == "Ввести всё сразу":
        await state.set_state(Form.waiting_for_full_text)
        await message.reply(
            "Пожалуста, ведите ю информацию о себе одним сообщением:\n"
            "ФИО, пол, озраст, регион, семейное положение, количество детей, "
            "наличие соц. посоий.",
            reply_markup=ReplyKeyboardRemove()
        )

# Пошаговый ввод данных
@router.message(Form.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(Form.waiting_for_gender)
    await message.reply("Укажите ваш пол:", reply_markup=gender_kb)

@router.message(Form.waiting_for_gender)
async def process_gender(message: types.Message, state: FSMContext):
    if message.text not in ["Мужской", "Женский"]:
        await message.reply("Пожалуйста, ипольуйте кнопки для выбора пола.")
        return
    await state.update_data(gender=message.text)
    await state.set_state(Form.waiting_for_age)
    await message.reply("Укажите ваш возраст:", reply_markup=ReplyKeyboardRemove())

@router.message(Form.waiting_for_age)
async def process_age(message: types.Message, state: FSMContext):
    # Проверяем, что введено чисо
    if not message.text.isdigit():
        await message.reply("Пожалуйста, введите возраст цифрами.")
        return
    
    age = int(message.text)
    # Проверяе адекватность возраста
    if age < 0 or age > 120:
        await message.reply("Пожалуйста, введите корректный возраст (от 0 до 120 лет).")
        return

    await state.update_data(age=message.text)
    await state.set_state(Form.waiting_for_region)
    await message.reply("Укажите ваш регион:", reply_markup=cities_kb)

@router.message(Form.waiting_for_region)
async def process_region(message: types.Message, state: FSMContext):
    if message.text not in KAZAKHSTAN_CITIES:
        await message.reply("Пожалуйста, выберит город из списка:", reply_markup=cities_kb)
        return
    
    # Сохраняем регион
    user_data = await state.get_data()
    user_data['region'] = message.text
    await state.update_data(region=message.text)
    
    # Проверяем следующий шаг
    await check_next_step(state, message)

@router.message(Form.waiting_for_marital_status)
async def process_marital(message: types.Message, state: FSMContext):
    valid_statuses = ["Холост/Не замужем", "Женат/Замужем", "В разводе", "Вдовец/Вдова"]
    if message.text not in valid_statuses:
        await message.reply("Пожалуйста, выберите вариант из предложенных:", reply_markup=marital_kb)
        return
    await state.update_data(marital_status=message.text)
    await state.set_state(Form.waiting_for_children)
    await message.reply("Укажите количество детей:", reply_markup=ReplyKeyboardRemove())

@router.message(Form.waiting_for_children)
async def process_children(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.reply("Пожалуйста, введите количество детей цифрами.")
        return
    
    children = int(message.text)
    if children < 0:
        await message.reply("Колчество детей не может быть отрицательным.")
        return

    await state.update_data(children=message.text)
    await state.set_state(Form.waiting_for_benefits)
    await message.reply("Получаете ли вы социальные пособия?", reply_markup=benefits_kb)

# Добавьте эту функцию для сохранения данных пользователя
@sync_to_async
def save_user_data_sync(user_id: int, user_data: dict):
    try:
        user = TelegramUser.objects.get(user_id=user_id)
        user.full_name = user_data.get('name')
        user.gender = user_data.get('gender')
        user.age = user_data.get('age')
        user.region = user_data.get('region')
        user.marital_status = user_data.get('marital_status')
        user.children = user_data.get('children')
        user.benefits = user_data.get('benefits')
        user.is_registered = True
        user.save()
        return True
    except Exception as e:
        logging.error(f"Error saving user data: {e}")
        return False

# Обновите обработчик benefits
@router.message(Form.waiting_for_benefits)
async def process_benefits(message: types.Message, state: FSMContext):
    if message.text not in ["Да", "Нет"]:
        await message.reply("ожалуйста, используйте кнопки для ответа.", reply_markup=benefits_kb)
        return
    
    user_data = await state.get_data()
    user_data['benefits'] = message.text
    
    # Проверяем наличие всех данных
    missing_fields = []
    if not user_data.get('name'): missing_fields.append('ФИО')
    if not user_data.get('gender'): missing_fields.append('пол')
    if not user_data.get('age'): missing_fields.append('возраст')
    if not user_data.get('region'): missing_fields.append('регион')
    if not user_data.get('marital_status'): missing_fields.append('семейное положение')
    if not user_data.get('children'): missing_fields.append('количество детей')
    if not user_data.get('benefits'): missing_fields.append('инормация о социальных пособиях')
    
    if missing_fields:
        # Определяем первое отсутствующее поле и соответствующую клавиатуру
        first_missing = missing_fields[0]
        keyboard = None
        prompt = f"У вас не хватает данных: {first_missing}. "
        
        if first_missing == 'пол':
            keyboard = gender_kb
            prompt += "Выберите ваш пол:"
            await state.set_state(Form.waiting_for_gender)
        elif first_missing == 'возраст':
            prompt += "Укажите ваш возраст:"
            await state.set_state(Form.waiting_for_age)
        elif first_missing == 'регион':
            keyboard = cities_kb
            prompt += "Выберите ваш регион:"
            await state.set_state(Form.waiting_for_region)
        elif first_missing == 'семейное положение':
            keyboard = marital_kb
            prompt += "Укажите ваше семейное полоение:"
            await state.set_state(Form.waiting_for_marital_status)
        elif first_missing == 'количество детей':
            prompt += "Укажите оличесво детей:"
            await state.set_state(Form.waiting_for_children)
        elif first_missing == 'ФИО':
            prompt += "Введите ваше ФИО:"
            await state.set_state(Form.waiting_for_name)
        elif first_missing == 'информация о социальных пособиях':
            keyboard = benefits_kb
            prompt += "олучаете ли вы социальные пособия?"
            await state.set_state(Form.waiting_for_benefits)
        
        await message.reply(prompt, reply_markup=keyboard)
        return
    
    # Если все данные есть, сохраняем их в базу
    save_success = await save_user_data_sync(message.from_user.id, user_data)
    
    if not save_success:
        await message.reply("Произошла ошибка при сохранении данных. Пожалуйста, попробуйте позже.")
        return
    
    # Формируем и отправляем сообщение
    formatted_message = (
        f"📋 Новая анкета:\n\n"
        f"👤 ФИО: {user_data['name']}\n"
        f" Пол: {user_data['gender']}\n"
        f"📅 Возраст: {user_data['age']}\n"
        f"🌍 Регион: {user_data['region']}\n"
        f"💑 Семейное положение: {user_data['marital_status']}\n"
        f"👶 Количество детей: {user_data['children']}\n"
        f"📦 Социальные пособия: {user_data['benefits']}"
    )
    
    # Отправляем в группу
    await bot.send_message(TARGET_GROUP_ID, formatted_message)
    await message.reply("Спасибо! Ваши данные успешно схранены.", reply_markup=functions_kb)
    await state.clear()

# Обновляем обработчик полного текста с GPT
@router.message(Form.waiting_for_full_text)
async def process_full_text(message: types.Message, state: FSMContext):
    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": """
                    Извлеки из текста следующие данные и верни их в формате JSON:
                    {
                        "name": "извлеченное ФИО",
                        "gender": "Мужской" если мужчина/мужской, "Женский" если женщина/женский, иначе None,
                        "age": извлеченный возраст числом, иначе None,
                        "region": извлеченный регион, иначе None,
                        "marital_status": "Холост/Не замужем" если уазано что холост/один/не женат,
                        "children": "0" если указано что нет етей,
                        "benefits": "Нет" если указано что нет пособий
                    }
                    """},
                {"role": "user", "content": message.text}
            ]
        )
        
        response_text = response.choices[0].message.content
        response_text = response_text.replace('null', 'None')
        parsed_data = eval(response_text)
        
        # Сохраняем данные
        await state.update_data(**parsed_data)
        
        # Проверяем только на отсутствующие данные
        if parsed_data.get('age') is None:
            await state.set_state(Form.waiting_for_age)
            await message.reply("У вас не указан возраст. Пожалуйста, укажите его:")
            return
        elif parsed_data.get('region') is None:
            await state.set_state(Form.waiting_for_region)
            await message.reply("У вас не указан регион. Пожалуйста, выберте:", reply_markup=cities_kb)
            return
        elif parsed_data.get('gender') is None:
            await state.set_state(Form.waiting_for_gender)
            await message.reply("У вас не указан пол. Пожалуйста, выберите:", reply_markup=gender_kb)
            return
            
        # Если все данные есть, отправляем сообщение
        formatted_message = (
            f"📋 Новая анкета:\n\n"
            f"👤 ФИО: {parsed_data['name']}\n"
            f"⚤ Пол: {parsed_data['gender']}\n"
            f"📅 Возраст: {parsed_data['age']}\n"
            f"🌍 Регион: {parsed_data['region']}\n"
            f"💑 Семейное положение: {parsed_data['marital_status']}\n"
            f"👶 Количество детей: {parsed_data['children']}\n"
            f"📦 Социальные пособия: {parsed_data['benefits']}"
        )
        
        await bot.send_message(TARGET_GROUP_ID, formatted_message)
        await message.reply("Спасибо! Ваши данные успешно отправлены.", reply_markup=ReplyKeyboardRemove())
        await state.clear()
        
        # Добавляем вызов меню функций
        await message.reply(
            "Теперь вы можете использовать наши функции. Выберите интересующую вас тему:",
            reply_markup=functions_kb
        )
        
        # После успешно обработи текста добавьте:
        save_success = await save_user_data_sync(message.from_user.id, parsed_data)
        
        if not save_success:
            await message.reply("Произошла ошибка при сохранении данных. Пожалуйста, попробуйте позже.")
            return
        
    except Exception as e:
        print(f"Error: {e}")
        await message.reply(
            "Извиние, произоша ошбка при обработке текста. "
            "Пожалуйста, проверьте формат введенных данных и попробуйте снова."
        )

@router.message(Form.waiting_for_gender)
async def process_gender_after_text(message: types.Message, state: FSMContext):
    if message.text not in ["Мужской", "Женский"]:
        await message.reply("Пожалуйста, исполуйте кнопки для выбора пола.", reply_markup=gender_kb)
        return
        
    await state.update_data(gender=message.text)
    user_data = await state.get_data()
    
    # Проверяем следующее пропущенне поле
    if not user_data.get('age'):
        await state.set_state(Form.waiting_for_age)
        await message.reply("Отлично! Теперь кажите ваш возраст:", reply_markup=ReplyKeyboardRemove())
        return
    elif not user_data.get('region'):
        await state.set_state(Form.waiting_for_region)
        await message.reply("кажите ваш регион:", reply_markup=cities_kb)
        return
    # ... и так далее для всех полей ...

@router.message(Form.waiting_for_region)
async def process_region_after_text(message: types.Message, state: FSMContext):
    if message.text not in KAZAKHSTAN_CITIES:
        await message.reply("Пожалуйста, выберите город из списка:", reply_markup=cities_kb)
        return
    
    try:
        # Полчаем сохраненные данные из первого анализа
        user_data = await state.get_data()
        
        # Добавлям только регион к существующим данным
        user_data['region'] = message.text
        
        # Сразу формируем и отправляем сообщение, использу все сохраненные данные
        formatted_message = (
            f"📋 Новая анкета:\n\n"
            f"👤 ФИО: {user_data['name']}\n"
            f"⚤ Пол: {user_data['gender']}\n"
            f"📅 Возраст: {user_data['age']}\n"
            f"🌍 Регион: {user_data['region']}\n"
            f"💑 Семейное положние: {user_data['marital_status']}\n"
            f"👶 Количество детей: {user_data['children']}\n"
            f"📦 Социальные пособия: {user_data['benefits']}"
        )
        
        # Отправляем сообщение и очищаем состояние
        await bot.send_message(TARGET_GROUP_ID, formatted_message)
        await message.reply("Спасибо! Ваши данные успешно тпавлены.", reply_markup=ReplyKeyboardRemove())
        await state.clear()  # Важно: очищаем состояние, чтобы прервать цикл опроса
        
    except Exception as e:
        print(f"Error: {e}")
        await message.reply(
            "Извините, произошла ошибка при обработке данных. "
            "Пожалуйста, попробуйте снова."
        )

@router.message(Form.waiting_for_age)
async def process_age_after_text(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.reply("Пожалуйста, введите возраст цифрами.")
        return
        
    age = int(message.text)
    if age < 0 or age > 120:
        await message.reply("Пожалуйста, введите корректный возраст (от 0 до 120 лет).")
        return
        
    # Получаем сораненные данные и добавляем возраст
    user_data = await state.get_data()
    user_data['age'] = message.text
    
    # Сразу формируем и отправляем сообщение
    formatted_message = (
        f"📋 Новая анкета:\n\n"
        f"👤 ФИО: {user_data['name']}\n"
        f"⚤ Пол: {user_data['gender']}\n"
        f"📅 Возраст: {user_data['age']}\n"
        f"🌍 Регион: {user_data['region']}\n"
        f"💑 Семейное положение: {user_data['marital_status']}\n"
        f"👶 Количество детей: {user_data['children']}\n"
        f"📦 Социальные пособия: {user_data['benefits']}"
    )
    
    await bot.send_message(TARGET_GROUP_ID, formatted_message)
    await message.reply("Отличо! Ваши данные успешно отправлены.", reply_markup=ReplyKeyboardRemove())
    await state.clear()
    
    # Добавляем вызов меню функци
    await message.reply(
        "Теперь вы можете использовать наши функции. Выерите интересующую вас тему:",
        reply_markup=functions_kb
    )

# Обработчик команды дя доступа к функциям
@router.message(Command("functions"))
async def cmd_functions(message: types.Message):
    await message.reply(
        "Выберите интересующую вас тему:",
        reply_markup=functions_kb
    )

# Обработчики для каждой функции
@router.message(lambda message: message.text == "Кибербезопасность")
async def process_cybersecurity(message: types.Message):
    try:
        # Сохраняем использование функции
        await save_user_request(
            message.from_user.id,
            message.from_user.username,
            "Кибербезопасность"
        )
        
        # Получаем ответ от GPT и отправляем пользователю
        response = await get_gpt_response(
            "Дай краткую информацию о текущем состоянии кибербезопасности и основных угрозах"
        )
        await message.reply(response)
        
    except Exception as e:
        logging.error(f"Error in process_function: {e}")
        await message.reply("Произошла ошибка при обработке запроса. Попробуйте позже.")

@router.message(lambda message: message.text == "Финансы")
async def process_finance(message: types.Message):
    try:
        # Сохраняем использование функции
        await save_user_request(
            message.from_user.id,
            message.from_user.username,
            "Финансы"
        )
        
        # Получаем ответ от GPT и отправляем пользователю
        response = await get_gpt_response(
            "Дай кракий озор теущей финансовой ситуации и основных трендов"
        )
        await message.reply(response)
        
    except Exception as e:
        logging.error(f"Error in process_function: {e}")
        await message.reply("Произошла ошибка при обработке запроса. Попробуйте позже.")

@router.message(lambda message: message.text == "риптовалюты")
async def process_crypto(message: types.Message):
    try:
        # Сохраняем использование функции
        await save_user_request(
            message.from_user.id,
            message.from_user.username,
            "Криптовалюты"
        )
        
        # Получаем ответ от GPT и отправляем пользователю
        response = await get_gpt_response(
            "Дай краткий обзор текущей ситуации на крипторынке и основных трендов"
        )
        await message.reply(response)
        
    except Exception as e:
        logging.error(f"Error in process_function: {e}")
        await message.reply("Произошла ошибка при обработке запроса. Попробуйте позже.")

@router.message(lambda message: message.text == "Инвестиции")
async def process_investments(message: types.Message):
    try:
        # Сохраняем использование функции
        await save_user_request(
            message.from_user.id,
            message.from_user.username,
            "Инвестиции"
        )
        
        # Получаем ответ от GPT и отправляем пользователю
        response = await get_gpt_response(
            "Дай краткий обзор инвестиционных возможностей и текущих трендов"
        )
        await message.reply(response)
        
    except Exception as e: 
        logging.error(f"Error in process_function: {e}")
        await message.reply("Произошла ошибка при обработке запроса. Попробуйте позже.")

@router.message(lambda message: message.text == "Стартапы")
async def process_startups(message: types.Message):
    try:
        # Сохраняем использование функции
        await save_user_request(
            message.from_user.id,
            message.from_user.username,
            "Стартапы"
        )
        
        # Получаем ответ от GPT и отправляем пользователю
        response = await get_gpt_response(
            "Дай краткий обзор стартап-экосистемы и актуальных направлений"
        )
        await message.reply(response)
        
    except Exception as e:
        logging.error(f"Error in process_function: {e}")
        await message.reply("Произошла ошибка при обработке запроса. Попробуйте позже.")

@router.message(lambda message: message.text == "Технологии")
async def process_tech(message: types.Message):
    try:
        # Сохраняем использование функции
        await save_user_request(
            message.from_user.id,
            message.from_user.username,
            "Технологии"
        )
        
        # Получаем ответ от GPT и отправляем пользователю
        response = await get_gpt_response(
            "Дай краткий обзор последних технологических трендов и инноваций"
        )
        await message.reply(response)
        
    except Exception as e:
        logging.error(f"Error in process_function: {e}")
        await message.reply("Произошла ошибка при обработке запроса. Попробуйте позже.")

@router.message(lambda message: message.text == "Искусственный интеллект")
async def process_ai(message: types.Message):
    try:
        # Сохраняем использование функции
        await save_user_request(
            message.from_user.id,
            message.from_user.username,
            "Искусственный интеллект"
        )
        
        # Получаем ответ от GPT и отправляем пользователю
        response = await get_gpt_response(
            "Дай краткий обзор последних достижений в области ИИ и его применения"
        )
        await message.reply(response)
        
    except Exception as e:
        logging.error(f"Error in process_function: {e}")
        await message.reply("Произошла ошибка при обработке запроса. Попробуйте позже.")

@router.message(lambda message: message.text == "Маркетинг")
async def process_marketing(message: types.Message):
    try:
        # Сохраняем использование функции
        await save_user_request(
            message.from_user.id,
            message.from_user.username,
            "Маркетинг"
        )
        
        # Получаем ответ от GPT и отправляем пользователю
        response = await get_gpt_response(
            "Дай краткий обзор соврменных маркетинговых стратегий и трендов"
        )
        await message.reply(response)
        
    except Exception as e:
        logging.error(f"Error in process_function: {e}")
        await message.reply("Произошла ошибка при обработке запроса. Попробуйте позже.")

@router.message(lambda message: message.text == "Бизнес")
async def process_business(message: types.Message):
    try:
        # Сохраняем использование функции
        await save_user_request(
            message.from_user.id,
            message.from_user.username,
            "Бизнес"
        )
        
        # Получаем ответ от GPT и отправляем пользователю
        response = await get_gpt_response(
            "Дай кракий обзор текущей бизнес-среды и перспективных направлений"
        )
        await message.reply(response)
        
    except Exception as e:
        logging.error(f"Error in process_function: {e}")
        await message.reply("Произошла ошибка при обработке запроса. Попробуйте позже.")

@router.message(lambda message: message.text == "Образование")
async def process_education(message: types.Message):
    try:
        # Сохраняем использование функции
        await save_user_request(
            message.from_user.id,
            message.from_user.username,
            "Образование"
        )
        
        # Получаем ответ от GPT и отправляем пользователю
        response = await get_gpt_response(
            "Дай краткий обзор современных тенденций в образовании и перспективых направлений"
        )
        await message.reply(response)
        
    except Exception as e:
        logging.error(f"Error in process_function: {e}")
        await message.reply("Произошла ошибка при обработке запроса. Попробуйте позже.")

# Функция для получения ответа от GPT
async def get_gpt_response(prompt: str) -> str:
    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты эксперт, который дает краткие и информативные ответы"},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"GPT Error: {e}")
        return "Извините, произошла ошибка при получении информации. Попробуйте позже."

@router.message(Command("menu"))
async def cmd_menu(message: types.Message):
    await message.reply(
        "Выберите интересующую вас тему:",
        reply_markup=functions_kb
    )

# Добавьте эту вспомогательную функцию
async def check_next_step(state: FSMContext, message: types.Message):
    user_data = await state.get_data()
    
    # Проверяем каждое поле по порядку
    if not user_data.get('marital_status'):
        await state.set_state(Form.waiting_for_marital_status)
        await message.reply("Укажите ваше семейное положение:", reply_markup=marital_kb)
        return True
    elif not user_data.get('children'):
        await state.set_state(Form.waiting_for_children)
        await message.reply("Укажите количество детей:", reply_markup=ReplyKeyboardRemove())
        return True
    elif not user_data.get('benefits'):
        await state.set_state(Form.waiting_for_benefits)
        await message.reply("Получаете ли вы социальные пособия?", reply_markup=benefits_kb)
        return True
    
    # Если все данные собраны, завершаем регистрацию
    await complete_registration(message, state, user_data)
    return False

# Доавьте функцию завершения регистрации
async def complete_registration(message: types.Message, state: FSMContext, user_data: dict):
    formatted_message = (
        f"📋 Новая анкета:\n\n"
        f"👤 ФИО: {user_data['name']}\n"
        f"⚤ Пол: {user_data['gender']}\n"
        f"📅 Возраст: {user_data['age']}\n"
        f"🌍 Регин: {user_data['region']}\n"
        f"💑 Семейное положение: {user_data['marital_status']}\n"
        f"👶 Количество детей: {user_data['children']}\n"
        f"📦 Социальные пособия: {user_data['benefits']}"
    )
    
    # Сохраняем данные в базу
    save_success = await save_user_data_sync(message.from_user.id, user_data)
    
    if not save_success:
        await message.reply("Произошла ошибка при сохранении данных. Пожалуйста, попробуйте позже.")
        return
    
    await bot.send_message(TARGET_GROUP_ID, formatted_message)
    await message.reply("Спасибо! Ваши данные успешно сохранены.", reply_markup=ReplyKeyboardRemove())
    await state.clear()
    
    await message.reply(
        "Теперь вы можете использовать наши функции. Выберите интересующую вас тему:",
        reply_markup=functions_kb
    )

# Функция для создания клавиатуры с вопросами
def create_quiz_kb(topics):
    keyboard = []
    for topic in topics:
        row = []
        emoji = QUIZ_EMOJIS.get(topic, '❓')
        for points in [50, 100, 150]:
            callback_data = f"quiz:{topic}:{points}"
            row.append(InlineKeyboardButton(
                text=f"{emoji}{points}",
                callback_data=callback_data
            ))
        keyboard.append(row)
    
    # Добавляем кнопку возврата в главное меню
    keyboard.append([InlineKeyboardButton(
        text="Вернуться в главное меню",
        callback_data="quiz:menu"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@router.message(lambda message: message.text == "Проверить себя")
async def start_quiz(message: types.Message, state: FSMContext):
    user = await sync_to_async(TelegramUser.objects.get)(user_id=message.from_user.id)
    if not user.used_functions:
        await message.reply("Сначала изучите хотя бы одну тему!")
        return
    
    topics = list(user.used_functions)
    topics = topics[:3] if len(topics) > 3 else topics
    
    if not topics:
        await message.reply("Сначала изучите хотя бы одну тему!")
        return

    # Получаем данные о пройденных вопросах
    data = await state.get_data()
    used_buttons = data.get('used_buttons', [])
    correct_answers = data.get('correct_answers', [])  # Новый список для правильных ответов

    # Проверяем, все ли вопросы пройдены
    all_questions = sum(1 for t in topics for _ in range(3))  # 3 вопроса на каждую тему
    if len(used_buttons) >= all_questions:
        await message.reply(
            f"🎓 Вы уже прошли все вопросы!\n"
            f"💫 Ваши текущие очки: {user.quiz_points}\n"
            f"👋 Возвращайтесь в следующий раз!"
        )
        return

    # Очищаем использованные кнопки при новом запуске квиза
    await state.update_data(
        available_topics=topics,
        used_buttons=used_buttons,
        correct_answers=correct_answers
    )
    
    topics_text = "\n".join([f"{QUIZ_EMOJIS.get(topic, '❓')} {topic}" for topic in topics])
    quiz_message = await message.reply(
        f"<b>Викторина!</b>\n\n"
        f"🎯 Ваши текущие очки: {user.quiz_points}\n\n"
        f"Доступные темы:\n{topics_text}\n\n"
        f"Выбирайте вопрос:",
        reply_markup=create_quiz_kb(topics, used_buttons, correct_answers),
        parse_mode="HTML"
    )
    
    await state.update_data(quiz_messages=[quiz_message.message_id])

# Обновляем функцию создания клавиатуры
def create_quiz_kb(topics, used_buttons, correct_answers):
    keyboard = []
    for t in topics:
        row = []
        for p in [50, 100, 150]:
            button_id = f"{t}:{p}"
            if button_id in used_buttons:
                # Используем ✅ для правильных ответов и ❌ для неправильных
                text = "✅" if button_id in correct_answers else "❌"
                row.append(InlineKeyboardButton(text=text, callback_data=f"quiz:used:{t}:{p}"))
            else:
                emoji = QUIZ_EMOJIS.get(t, '❓')
                row.append(InlineKeyboardButton(text=f"{emoji}{p}", callback_data=f"quiz:{t}:{p}"))
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton(text="Вернуться в главное меню", callback_data="quiz:menu")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Обновляем обработчик ответов на опросы
@router.poll_answer()
async def handle_poll_answer(poll_answer: types.PollAnswer, state: FSMContext):
    try:
        user = await sync_to_async(TelegramUser.objects.get)(user_id=poll_answer.user.id)
        data = await state.get_data()
        
        if not data.get('current_question'):
            return
        
        question_data = data['current_question']
        points = question_data['points']
        correct_answer = data.get('correct_answer', '')
        explanation = data.get('explanation', '')
        
        # Получаем списки использованных кнопок и правильных ответов
        used_buttons = data.get('used_buttons', [])
        correct_answers = data.get('correct_answers', [])
        current_button = f"{question_data['topic']}:{points}"

        # Проверяем правильность ответа и обновляем очки
        if poll_answer.option_ids[0] == 0:
            user.quiz_points += points
            correct_answers.append(current_button)  # Добавляем в список правильных ответов
            response_text = (
                f"🎉 <b>Верно!</b>\n"
                f"Текущие очки: {user.quiz_points}\n\n"
                f"{explanation}\n\n"
                f"Выберите следующий вопрос:"
            )
        else:
            user.quiz_points -= points
            response_text = (
                f"😢 <b>Неверно</b>\n"
                f"Текущие очки: {user.quiz_points}\n\n"
                f"Правильный ответ: {correct_answer}\n\n"
                f"{explanation}\n\n"
                f"Выберите следующий вопрос:"
            )
        
        await sync_to_async(user.save)()
        
        # Проверяем, все ли вопросы пройдены
        topics = data.get('available_topics', [])
        all_questions = sum(1 for t in topics for _ in range(3))
        if len(used_buttons) >= all_questions:
            response_text = (
                f"🎓 Поздравляем! Вы прошли все вопросы!\n"
                f"💫 Ваши итоговые очки: {user.quiz_points}\n"
                f"👋 Возвращайтесь в следующий раз!"
            )
        
        # Обновляем состояние
        await state.update_data(
            used_buttons=used_buttons,
            correct_answers=correct_answers
        )
        
        # Отправляем сообщение с результатом и обновленной клавиатурой
        await bot.send_message(
            poll_answer.user.id,
            response_text,
            parse_mode="HTML",
            reply_markup=create_quiz_kb(topics, used_buttons, correct_answers)
        )

    except Exception as e:
        logging.error(f"Error in handle_poll_answer: {e}")
        await bot.send_message(
            poll_answer.user.id,
            "Произошла ошибка при обработке ответа."
        )

@router.callback_query(lambda c: c.data.startswith('quiz:'))
async def process_quiz_callback(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        await callback_query.answer()
        
        action = callback_query.data.split(':')
        
        # Проверяем, если это нажатие на использованный вопрос
        if action[1] == "used":
            await callback_query.answer("Этот вопрос уже был использован!", show_alert=True)
            return
            
        if action[1] == "menu":
            await state.clear()
            await callback_query.message.delete()
            await callback_query.message.answer(
                "Выберите интересующую вас тему:",
                reply_markup=functions_kb
            )
            return
        
        topic = action[1]
        points = int(action[2])
        
        data = await state.get_data()
        used_buttons = data.get('used_buttons', [])
        
        if f"{topic}:{points}" in used_buttons:
            await callback_query.answer("Этот вопрос уже был использован!")
            return
            
        question, correct, wrong1, wrong2, wrong3 = await get_quiz_question(topic, state)
        
        poll = await callback_query.message.answer_poll(
            question=f"Вопрос на тему \"{topic}\" за {points} очков\n\n{question}",
            options=[correct, wrong1, wrong2, wrong3],
            type='quiz',
            correct_option_id=0,
            is_anonymous=False
        )
        
        used_buttons.append(f"{topic}:{points}")
        await state.update_data(
            used_buttons=used_buttons,
            current_question={'topic': topic, 'points': points, 'poll_id': poll.poll.id}
        )
        
        # Обновляем клавиатуру
        topics = data.get('available_topics', [])
        new_keyboard = []
        for t in topics:
            row = []
            for p in [50, 100, 150]:
                if f"{t}:{p}" in used_buttons:
                    row.append(InlineKeyboardButton(text="❌", callback_data=f"quiz:used:{t}:{p}"))
                else:
                    emoji = QUIZ_EMOJIS.get(t, '❓')
                    row.append(InlineKeyboardButton(text=f"{emoji}{p}", callback_data=f"quiz:{t}:{p}"))
            new_keyboard.append(row)
        
        new_keyboard.append([InlineKeyboardButton(text="Вернуться в главное меню", callback_data="quiz:menu")])
        
        await callback_query.message.edit_reply_markup(
            reply_markup=InlineKeyboardMarkup(inline_keyboard=new_keyboard)
        )
        
    except Exception as e:
        logging.error(f"Error in process_quiz_callback: {e}")
        await callback_query.message.answer(
            "Произошла ошибка при генерации вопроса. Попробуйте еще раз."
        )

@router.callback_query(lambda c: c.data.startswith('quiz:used:'))
async def process_used_button(callback_query: types.CallbackQuery):
    await callback_query.answer("Этот вопрос уже был использован!", show_alert=True)

async def get_quiz_question(topic: str, state: FSMContext) -> tuple:
    try:
        system_prompt = """Ты создаешь вопросы для викторины. 
        Каждый ответ должен быть конкретным вариантом, а не placeholder.
        После вопроса нужно дать объяснение.
        
        Пример правильного формата:
        Какая криптовалюта была создана первой?|Bitcoin|Ethereum|Litecoin|Dogecoin|Bitcoin был создан в 2009 году Сатоши Накамото и стал первой криптовалютой в мире.
        
        Твй ответ должен строго следовать формату:
        ВОПРОС|ПРАВИЛЬНЫЙ_ОТВЕТ|НЕВЕРНЫЙ_ОТВЕТ_1|НЕВЕРНЫЙ_ОТВЕТ_2|НЕВЕРНЫЙ_ОТВЕТ_3|ОБЪЯСНЕНИЕ
        
        Не добавляй никаких дополнительных символов или текста."""
        
        user_prompt = f"Создай один вопрос с 4 конкретными вариантами ответа по теме {topic}. Ответ должен строго соответствовать формату, разделенному символами |"
        
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7
        )
        
        raw_response = response.choices[0].message.content.strip()
        parts = [part.strip() for part in raw_response.split('|')]
        
        if len(parts) != 6:
            raise ValueError("Неверный формат ответа от GPT")
        
        question, correct, wrong1, wrong2, wrong3, explanation = parts
        
        await state.update_data({
            'correct_answer': correct,
            'explanation': explanation
        })
        
        return (question, correct, wrong1, wrong2, wrong3)
        
    except Exception as e:
        logging.error(f"GPT Quiz Error: {e}")
        return (
            f"Что из перечисленного относится к теме {topic}?",
            f"Основной элемент {topic}",
            f"Не относится к {topic}",
            f"Совсем другая тема",
            f"Противоположное понятие"
        )

# Обработчик кнопки "Личный кабинет"
@router.message(lambda message: message.text == "Личный кабинет")
async def show_profile(message: types.Message):
    try:
        user = await sync_to_async(TelegramUser.objects.get)(user_id=message.from_user.id)
        
        profile_text = (
            f"👤 <b>Ваш профиль:</b>\n\n"
            f"ФИО: {user.full_name or 'е указано'}\n"
            f"Пол: {user.gender or 'Не указано'}\n"
            f"Возраст: {user.age or 'Не указано'}\n"
            f"Регион: {user.region or 'Не указано'}\n"
            f"Семейное положение: {user.marital_status or 'Не указано'}\n"
            f"Количество детей: {user.children or 'Не указано'}\n"
            f"Социальные пособия: {user.benefits or 'Не указано'}\n\n"
            f"🎯 Набрано очков в викторине: {user.quiz_points}\n"
            f"📚 Изученные темы: {', '.join(user.used_functions) if user.used_functions else 'Нет'}"
        )
        
        await message.answer(profile_text, reply_markup=profile_kb, parse_mode="HTML")
        
    except Exception as e:
        logging.error(f"Error in show_profile: {e}")
        await message.answer("Произошла ошибка при получении данных профиля.")

# Обработчик кнопок личного кабинета
@router.callback_query(lambda c: c.data.startswith('profile:'))
async def process_profile_callback(callback_query: types.CallbackQuery, state: FSMContext):
    action = callback_query.data.split(':')[1]
    
    if action == "menu":
        await callback_query.message.delete()
        await callback_query.message.answer("Выберите интересующую вас тему:", reply_markup=functions_kb)
    elif action == "edit":
        await callback_query.message.edit_text(
            "Выберите, что хотите изменить:",
            reply_markup=edit_kb
        )

# Обработчик кнопок редактирования
@router.callback_query(lambda c: c.data.startswith('edit:'))
async def process_edit_callback(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        field = callback_query.data.split(':')[1]
        
        if field == "back":
            # Возвращаемся к профилю
            await show_profile(callback_query.message)
            return
            
        field_names = {
            "full_name": "ФИО",
            "age": "возраст",
            "region": "регион",
            "marital_status": "семейное положение",
            "children": "количество детей",
            "benefits": "социальные пособия"
        }
        
        await state.update_data(editing_field=field)
        await state.set_state(Form.editing_field)
        
        # Специальные клавиатуры для определенных полей
        keyboard = None
        if field == "marital_status":
            keyboard = marital_kb
        elif field == "benefits":
            keyboard = benefits_kb
        elif field == "region":
            keyboard = cities_kb
            
        await callback_query.message.edit_text(
            f"Введите новое значение для поля '{field_names[field]}':",
            reply_markup=keyboard
        )
        
    except Exception as e:
        logging.error(f"Error in process_edit_callback: {e}")
        await callback_query.message.answer("Произошла ошибка при редактировании.")

# Обработчик ввода нового значения
@router.message(Form.editing_field)
async def process_edit_value(message: types.Message, state: FSMContext):
    try:
        data = await state.get_data()
        field = data['editing_field']
        
        # Валидация введенных данных
        if field == "age" and not message.text.isdigit():
            await message.reply("Пожалуйста, введите корректный возраст цифрами.")
            return
            
        user = await sync_to_async(TelegramUser.objects.get)(user_id=message.from_user.id)
        
        # Обновляем поле
        setattr(user, field, message.text)
        await sync_to_async(user.save)()
        
        await state.clear()
        await message.answer("Данные успешно обновлены!")
        
        # Показываем обновленный профиль
        await show_profile(message)
        
    except Exception as e:
        logging.error(f"Error in process_edit_value: {e}")
        await message.answer("Произошла ошибка при сохранении данных.")

# Обработчик кнопки поиска
@router.message(lambda message: message.text == "🔍 Поиск пользователя")
async def start_user_search(message: types.Message, state: FSMContext):
    await state.set_state(Form.waiting_for_user_search)
    await message.reply(
        "Введите ID пользователя или ФИО для поиска:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Отмена")]],
            resize_keyboard=True
        )
    )
API_BASE_URL = 'http://127.0.0.1:8000/'
# Обработчик поискового запроса
@router.message(Form.waiting_for_user_search)
async def process_user_search(message: types.Message, state: FSMContext):
    if message.text == "Отмена":
        await state.clear()
        await message.reply(
            "Поиск отменен. Выберите действие:",
            reply_markup=functions_kb
        )
        return

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                urljoin(API_BASE_URL, 'api/get_user_data/'),
                json={'query': message.text}
            ) as response:
                result = await response.json()
                
                if result['status'] == 'success':
                    user_data = result['data']
                    response_text = (
                        f"📋 Данные пользователя:\n\n"
                        f"🆔 ID: {user_data['user_id']}\n"
                        f"👤 Имя пользователя: {user_data['username']}\n"
                        f"📝 ФИО: {user_data['full_name']}\n"
                        f"⚤ Пол: {user_data['gender']}\n"
                        f"📅 Возраст: {user_data['age']}\n"
                        f"🌍 Регион: {user_data['region']}\n"
                        f"💑 Семейное положение: {user_data['marital_status']}\n"
                        f"👶 Количество детей: {user_data['children']}\n"
                        f"📦 Социальные пособия: {user_data['benefits']}\n"
                        f"🎯 Очки викторины: {user_data['quiz_points']}\n"
                        f"📚 Изученные темы: {', '.join(user_data['used_functions'])}\n"
                        f"⏱ Последняя активность: {user_data['last_activity']}"
                    )
                else:
                    response_text = f"❌ Ошибка: {result.get('error', 'Неизвестная ошибка')}"
                
                await message.reply(response_text, reply_markup=functions_kb)
                await state.clear()
                
    except Exception as e:
        logging.error(f"Error in user search: {e}")
        await message.reply(
            "Произошла ошибка при поиске. Попробуйте позже.",
            reply_markup=functions_kb
        )
        await state.clear()

async def main():
    # Включаем роутер
    dp.include_router(router)
    
    # Запускаем бота
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
