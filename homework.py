import os
import time
import logging
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from telebot import TeleBot
from telebot.apihelper import ApiException

from exceptions import EnvironmentError

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверка переменных окружения."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    check = []
    for name_token, token in tokens.items():
        if not token:
            check.append(name_token)
    if check:
        message = f'Отсутствует переменная(ые) окружения: {", ".join(check)}'
        logging.critical(message)
        raise EnvironmentError(message)


def send_message(bot, message):
    """Отправка смс в чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except ApiException as error:
        logging.error(f'Сбой при отправке сообщения: {error}')
        return False
    logging.debug(f'Сообщение отправлено - {message}')
    return True


def get_api_answer(timestamp):
    """Запрос к эедпоинту API сервиса."""
    api_request_config = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': timestamp}
    }
    logging.info(
        f'Отправка запроса к {api_request_config["url"]} с параметрами:'
        f'{api_request_config["headers"]} и {api_request_config["params"]}'
    )

    try:
        response = requests.get(**api_request_config)
    except requests.RequestException:
        raise ConnectionError(
            f'Ошибка при запросе к эндпоинту {api_request_config["url"]} '
            f'с параметрами: {api_request_config["headers"]} и '
            f'{api_request_config["params"]}'
        )
    if response.status_code != HTTPStatus.OK:
        raise ConnectionError('Ошибка при запросе к '
                              f'эндпоинту {api_request_config["url"]} '
                              f'с параметрами: {api_request_config["params"]}')

    try:
        response_json = response.json()
    except ValueError as e:
        raise ValueError(f'Ошибка при преобразовании ответа в JSON: {e}')

    return response_json


def check_response(response):
    """Проверка корректности API ответа."""
    if not isinstance(response, dict):
        raise TypeError('Некорректный формат ответа API: ожидается словарь')

    if 'homeworks' not in response:
        raise KeyError('Ключ "homeworks" отсутствует в ответе API')
    list_home_works = response.get('homeworks')

    if not isinstance(list_home_works, list):
        raise TypeError('Некорректный формат данных о домашних'
                        'работах в ответе API')
    return list_home_works


def parse_status(homework):
    """Извечение статус домашней работы."""
    homework_name = homework.get('homework_name')
    status = homework.get('status')

    if homework_name is None or status is None:
        raise KeyError('Отсутствует ключ "homework_name" '
                       'или "status" в объекте homework')

    if status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Неверный статус домашней работы: {status}')

    return ('Изменился статус проверки '
            f'работы "{homework_name}". {HOMEWORK_VERDICTS.get(status)}')


def main():
    """Основная логика работы бота."""
    logging.error('Бот запущен')
    check_tokens()
    last_status = ''
    # Создаем объект класса бота
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = 0

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if not homeworks:
                logging.debug('Получен пустой список домашних работ')
                continue
            status_home_work = parse_status(homeworks[0])
            if send_message(bot, status_home_work):
                last_status = status_home_work
                timestamp = response.get('current_date', timestamp)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            if last_status != message and send_message(bot, message):
                last_status = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    log_dir = os.path.dirname(os.path.abspath(__file__))
    log_file_path = os.path.join(log_dir, 'homework.log')
    file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
    stream_handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s - %(pathname)s - %(lineno)d'
    )
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)
    logging.basicConfig(handlers=[file_handler, stream_handler])
    main()
