# Импорт необходимых библиотек
import os  # Для работы с окружением и .env
import asyncio  # Для асинхронного кода (aiogram асинхронный)
from dotenv import load_dotenv  # Для загрузки переменных из .env
from aiogram import Bot, Dispatcher  # Основные компоненты aiogram
from aiogram.filters import CommandStart, Command  # Фильтры для команд
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton  # Для сообщений и клавиатуры
from mistralai import Mistral  # Клиент для Mistral API (из документации https://docs.mistral.ai/)

# Загружаем переменные из .env
load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')  # Токен Telegram-бота
MISTRAL_API_KEY = os.getenv('MISTRAL_API_KEY')  # Ключ Mistral API

# Инициализация бота и диспетчера
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# Создаём меню управления (ReplyKeyboardMarkup)
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Генерировать пост")],  # Кнопка для запуска генерации
        [KeyboardButton(text="Помощь")]  # Кнопка для помощи
    ],
    resize_keyboard=True,  # Автоматический размер
    one_time_keyboard=False  # Клавиатура не скрывается после нажатия
)


# Хэндлер для команды /start (приветственное сообщение)
@dp.message(CommandStart())
async def send_welcome(message: Message):
    # Приветственное сообщение с описанием
    welcome_text = (
        "Привет! Я бот для генерации постов с текстом и изображением через Mistral AI.\n"
        "Возможности:\n"
        "- Отправь мне промпт (текст), и я сгенерирую пост с текстом и картинкой.\n"
        "- Используй меню для управления.\n"
        "Нажми 'Генерировать пост' или просто напиши промпт."
    )
    await message.answer(welcome_text, reply_markup=main_menu)  # Отправляем с меню


# Хэндлер для команды /help или кнопки "Помощь"
@dp.message(Command('help'))
@dp.message(lambda message: message.text == "Помощь")
async def send_help(message: Message):
    help_text = "Инструкция:\n- Напиши промпт, например: 'Пост о закате на море'.\n- Я отправлю его в Mistral API и верну текст + изображение."
    await message.answer(help_text, reply_markup=main_menu)


# Хэндлер для кнопки "Генерировать пост" (просит ввести промпт)
@dp.message(lambda message: message.text == "Генерировать пост")
async def ask_for_prompt(message: Message):
    await message.answer("Введите промпт для генерации поста:", reply_markup=main_menu)


# Хэндлер для любого текстового сообщения (считаем его промптом)
@dp.message()
async def generate_post(message: Message):
    prompt = message.text  # Получаем текст от пользователя как промпт

    # Инициализируем клиент Mistral (из документации https://docs.mistral.ai/getting-started/quickstart/)
    client = Mistral(api_key=MISTRAL_API_KEY)

    try:
        # Отправляем запрос в Mistral API для генерации текста и изображения
        # Используем chat.complete с моделью (например, mistral-large-latest)
        # Для изображений: предполагаем использование агента с tool 'image_generation' (см. docs.mistral.ai/agents/connectors/image_generation/)
        # В реальности настрой агент в консоли и укажи его ID. Здесь пример с базовым chat.
        chat_response = client.chat.complete(
            model="mistral-large-latest",  # Модель из docs
            messages=[
                {"role": "user",
                 "content": f"Сгенерируй пост: {prompt}. Включи текст и сгенерируй изображение через tool."}
            ],
            # Для агентов с изображениями: добавьте tools (пример из docs)
            tools=[{  # Пример инструмента для image generation (адаптировано из docs[13])
                "type": "function",
                "function": {
                    "name": "generate_image",
                    "description": "Generate an image based on prompt",
                    "parameters": {
                        "type": "object",
                        "properties": {"prompt": {"type": "string"}},
                        "required": ["prompt"]
                    }
                }
            }],
            tool_choice="auto"  # Автоматический выбор инструмента
        )

        # Получаем текст из ответа (первый choice)
        generated_text = chat_response.choices[0].message.content

        # Для изображения: в ответе от агента может быть вызов инструмента с URL изображения
        # Здесь упрощённо: предполагаем, что в ответе есть URL изображения (в реальности парсите tool_calls)
        # Если tool вызван, Mistral вернёт tool_calls с результатом (URL изображения)
        image_url = None
        if chat_response.choices[0].message.tool_calls:
            # Пример парсинга (в реальности обработайте вызов инструмента)
            tool_call = chat_response.choices[0].message.tool_calls[0]
            if tool_call.function.name == "generate_image":
                # Здесь должно быть выполнение инструмента, но Mistral обрабатывает встроенные connectors
                # Для примера: предположим, URL возвращается в аргументах или последующем вызове
                image_url = "https://example.com/generated_image.jpg"  # Замените на реальный парсинг

        # Отправляем ответ пользователю в одном сообщении
        if image_url:
            await message.answer_photo(photo=image_url, caption=generated_text)  # Изображение с текстом
        else:
            await message.answer(generated_text + "\n(Изображение не сгенерировано, проверьте настройку агента.)")

    except Exception as e:
        await message.answer(f"Ошибка: {str(e)}. Проверьте API ключ и документацию Mistral.")


# Основная функция для запуска бота
async def main():
    await dp.start_polling(bot)  # Запускаем polling (опрос обновлений)


# Запуск
if __name__ == '__main__':
    asyncio.run(main())
