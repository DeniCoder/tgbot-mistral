import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram import F
from dotenv import load_dotenv

# Импорт клиента Mistral
from mistralai import Mistral

# Загрузка переменных окружения из .env
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

# Константы моделей Mistral (обновлённые идентификаторы)
TEXT_MODEL = "ministral-8b-2410"         # Точная модель для генерации текста
IMAGE_MODEL = "mistral-medium-2505"      # Модель для генерации изображений

# --- Инициализация Telegram бота и диспетчера ---
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# --- Инициализация клиента Mistral ---
client = Mistral(api_key=MISTRAL_API_KEY)

# --- Обработчик команды /start ---
@dp.message(CommandStart())
async def start_handler(message: types.Message):
    kb = ReplyKeyboardBuilder().add(types.KeyboardButton(text="🚀 Сгенерировать пост"))
    await message.answer(
        "Привет! Я могу сгенерировать пост и картинку по вашему описанию. Просто отправьте свой промпт в виде текста.",
        reply_markup=kb.as_markup(resize_keyboard=True)
    )

# --- Обработчик пользовательского промпта ---
@dp.message(F.text)
async def handle_prompt(message: types.Message):
    user_prompt = message.text.strip()
    await message.answer("⏳ Генерирую пост и изображение, пожалуйста, подождите...")

    # --- Генерация текста через Mistral ---
    try:
        chat_response = client.chat.complete(
            model=TEXT_MODEL,
            messages=[
                {"role": "system", "content": "Напиши короткий творческий пост по следующей теме."},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=180,
            temperature=0.8
        )
        generated_text = chat_response.choices[0].message.content
    except Exception as e:
        await message.answer(f"Ошибка при генерации текста: {e}")
        return

    # --- Генерация изображения через Mistral ---
    try:
        # Создаём агент с инструментом image_generation
        image_agent = client.beta.agents.create(
            model=IMAGE_MODEL,
            name="Image Generation Agent",
            description="Генерация изображений к постам.",
            instructions="Используй инструмент генерации картинок.",
            tools=[{"type": "image_generation"}],
            completion_args={
                "temperature": 0.3,
                "top_p": 0.95
            }
        )

        img_response = client.beta.conversations.start(
            agent_id=image_agent.id,
            inputs=user_prompt
        )

        # Обработка outputs, чтобы найти нужные части ответа
        # Обычно второй элемент outputs - MessageOutputEntry
        outputs = img_response.outputs
        msg_entry = None
        for entry in outputs:
            if getattr(entry, 'type', None) == 'message.output':
                msg_entry = entry
                break
        if not msg_entry:
            await message.answer("Ошибка: не найден message.output в ответе модели.")
            return

        file_id = None
        text_part = None
        for part in getattr(msg_entry, 'content', []):
            if getattr(part, 'type', None) == 'text':
                text_part = getattr(part, 'text', None)
            elif getattr(part, 'type', None) == 'tool_file':
                file_id = getattr(part, 'file_id', None)

        if not file_id:
            await message.answer("Ошибка: не найден файл изображения в ответе модели.")
            return

        # Скачиваем изображение
        file_bytes = client.files.download(file_id=file_id).read()
        image_path = "image_generated.png"
        with open(image_path, "wb") as f:
            f.write(file_bytes)

    except Exception as e:
        if "rate limit reached" in str(e):
            await message.answer(
                f"Лимит генерации изображений исчерпан, попробуйте еще раз через несколько минут.\n"
                f"Но вот сгенерированный пост: {generated_text}"
            )
            return
        await message.answer(f"Ошибка при генерации изображения: {e}")
        return

    try:
        # Отправка единым сообщением картинки и сгенерированного текста
        input_file = FSInputFile(image_path)
        # Используем текст именно как подпись к картинке
        caption_str = (generated_text or "Пост готов!").strip()
        await message.answer_photo(
            input_file,
            caption=caption_str
        )
    except Exception as e:
        await message.answer(f"Ошибка при отправке изображения: {e}")
    finally:
        # Удаление файла картинки после отправки
        if os.path.exists(image_path):
            os.remove(image_path)

# --- Основная точка входа ---
if __name__ == "__main__":
    # Запуск бота (асинхронно)
    asyncio.run(dp.start_polling(bot))
