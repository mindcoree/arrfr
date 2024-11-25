from .models import UserAction

def log_user_action(user, action_type, function_name=None):
    UserAction.objects.create(
        user=user,
        action_type=action_type,
        function_name=function_name
    )


import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression

def predict_user_activity(user_activity_data):
    """
    Предсказывает активность пользователей на основе предыдущих данных.

    :param user_activity_data: DataFrame с колонками ['date', 'activity_count']
    :return: прогнозируемое значение активности
    """
    # Преобразуем даты в числовой формат
    user_activity_data['days'] = (pd.to_datetime(user_activity_data['date']) - pd.to_datetime(user_activity_data['date']).min()).dt.days
    X = user_activity_data[['days']]
    y = user_activity_data['activity_count']

    # Линейная регрессия
    model = LinearRegression()
    model.fit(X, y)

    # Прогноз на 7 дней вперед
    future_days = np.array([[X['days'].max() + i] for i in range(1, 8)])
    predictions = model.predict(future_days)

    return predictions
