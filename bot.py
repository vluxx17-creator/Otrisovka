import asyncio, os, textwrap
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os
import textwrap

# Токен берём из переменной окружения Render
API_TOKEN = os.getenv("API_TOKEN")
if not API_TOKEN:
    raise ValueError("Не задан API_TOKEN в переменных окружения")

bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ---------- Состояния ----------
class FakeScreen(StatesGroup):
    waiting_for_name = State()
    waiting_for_review = State()

# ---------- Константы экрана iPhone X ----------
SCREEN_W, SCREEN_H = 1125, 2436
BG_TOP = (10, 132, 196)
BG_BOTTOM = (160, 215, 235)
HEADER_H = 175
STATUS_BAR_H = 80
CHAT_TOP_Y = HEADER_H + 20
BUBBLE_MARGIN = 30

# ---------- Подготовка шрифтов ----------
FONT_PATH = "SF-Pro-Text-Regular.otf"
FALLBACK_FONT_PATH = "Roboto-Regular.ttf"

def get_font(size):
    """Возвращает шрифт: сначала пробует SF Pro, потом Roboto, потом стандартный Pillow."""
    try:
        if os.path.exists(FONT_PATH):
            return ImageFont.truetype(FONT_PATH, size)
        elif os.path.exists(FALLBACK_FONT_PATH):
            return ImageFont.truetype(FALLBACK_FONT_PATH, size)
    except:
        pass
    return ImageFont.load_default()

font_time = get_font(28)
font_name = get_font(34)
font_status = get_font(24)
font_bubble = get_font(32)
font_small = get_font(24)

# ---------- Фон чата (градиент) ----------
def draw_chat_bg(draw, w, h):
    """Рисует вертикальный градиент от синего к голубому."""
    for y in range(h):
        r = int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * y / h)
        g = int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * y / h)
        b = int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * y / h)
        draw.line([(0, y), (w, y)], fill=(r, g, b))

# ---------- Круглая аватарка (или заглушка) ----------
def get_avatar_image(contact_name):
    """Загружает avatar.png или создаёт круг с инициалом."""
    avatar_size = 100
    if os.path.exists("avatar.png"):
        avatar = Image.open("avatar.png").convert("RGBA").resize((avatar_size, avatar_size))
    else:
        avatar = Image.new("RGBA", (avatar_size, avatar_size), (0,0,0,0))
        draw = ImageDraw.Draw(avatar)
        draw.ellipse([0, 0, avatar_size-1, avatar_size-1], fill=(100, 100, 100, 255))
        # Инициал
        letter = contact_name[0].upper() if contact_name else "A"
        font = get_font(40)
        # Центрируем букву
        bbox = draw.textbbox((0,0), letter, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        draw.text(((avatar_size - text_w)/2, (avatar_size - text_h)/2 - 5),
                  letter, fill="white", font=font)
    # Применяем круглую маску
    mask = Image.new("L", (avatar_size, avatar_size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse([0, 0, avatar_size, avatar_size], fill=255)
    avatar.putalpha(mask)
    return avatar

# ---------- Верхняя панель iOS + шапка чата ----------
def draw_header(draw, contact_name):
    """Рисует статус-бар и шапку с именем."""
    # Строка статуса
    draw.rectangle([0, 0, SCREEN_W, STATUS_BAR_H], fill=(0,0,0,0))
    draw.text((50, 20), "9:41", font=font_time, fill="white")
    # Иконка батареи
    draw.rectangle([SCREEN_W-100, 25, SCREEN_W-60, 55], outline="white", width=3)
    draw.rectangle([SCREEN_W-95, 30, SCREEN_W-65, 50], fill="white")
    draw.text((SCREEN_W-55, 20), "100%", font=font_small, fill="white")

    # Стрелка "Назад"
    draw.polygon([(40, 110), (70, 85), (70, 95), (100, 95),
                  (100, 125), (70, 125), (70, 135)], fill="white")

    # Аватар
    avatar = get_avatar_image(contact_name)
    avatar_x, avatar_y = 130, 85
    # Вставляем аватар с учётом альфа-канала
    # Для этого конвертируем основное изображение в RGBA, если ещё нет
    # Мы передаём ImageDraw, но он работает с изображением. Придётся вставить через само изображение.
    # Так как draw_header получает только ImageDraw, вернём изображение аватара, чтобы вставить позже.
    # Переделаем подход: будем возвращать avatar и координаты.
    return avatar, avatar_x, avatar_y

# ---------- Пузырь сообщения ----------
def draw_bubble(draw, text, is_outgoing, y_start):
    max_width = 600
    padding = 20
    lines = textwrap.wrap(text, width=25)
    # Вычисляем высоту строки
    sample_bbox = font_bubble.getbbox("Ay")
    line_height = sample_bbox[3] - sample_bbox[1] + 8
    bubble_height = len(lines) * line_height + padding * 2
    bubble_width = min(
        max(draw.textlength(line, font=font_bubble) for line in lines) + padding * 2,
        max_width
    )

    if is_outgoing:
        x0 = SCREEN_W - bubble_width - BUBBLE_MARGIN
        color = (0, 122, 255)
        text_color = (255, 255, 255)
    else:
        x0 = BUBBLE_MARGIN
        color = (229, 229, 234)
        text_color = (0, 0, 0)

    y0 = y_start
    radius = 20
    draw.rounded_rectangle([x0, y0, x0 + bubble_width, y0 + bubble_height],
                           radius=radius, fill=color)
    text_y = y0 + padding
    for line in lines:
        draw.text((x0 + padding, text_y), line, font=font_bubble, fill=text_color)
        text_y += line_height

    return y0 + bubble_height + 15

# ---------- Генерация скриншота ----------
async def generate_fake_screen(contact_name: str, review_text: str) -> str:
    # Создаём изображение с прозрачным фоном, потом зальём градиентом
    img = Image.new("RGBA", (SCREEN_W, SCREEN_H), (255,255,255,0))
    draw = ImageDraw.Draw(img)

    # 1. Фон чата
    draw_chat_bg(draw, SCREEN_W, SCREEN_H)

    # 2. Верхняя панель (возвращает аватар для вставки)
    avatar, av_x, av_y = draw_header(draw, contact_name)
    # Вставляем аватарку (используем alphacomposite)
    img.paste(avatar, (av_x, av_y), avatar)

    # 3. Сообщения
    y = CHAT_TOP_Y
    y = draw_bubble(draw, "Привет! Договорились, всё в силе?", False, y)
    y = draw_bubble(draw, "Да, вот реквизиты:\n2200 7008 1234 5678 (Сбер)", True, y)
    y = draw_bubble(draw, "Перевожу NFT, хэш:\n0x1a2b3c4d5e6f...", True, y)
    y = draw_bubble(draw, "Всё получил! Спасибо!", False, y)
    y = draw_bubble(draw, review_text, False, y)

    # 4. Сохраняем
    filepath = f"fake_{contact_name.replace(' ', '_')}.png"
    img.save(filepath)
    return filepath

# ---------- Обработчики команд ----------
@dp.message(Command("start"))
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Привет! Отправь /fake_review, чтобы создать скриншот переписки с отзывом.")

@dp.message(Command("fake_review"))
async def ask_name(message: types.Message, state: FSMContext):
    await state.set_state(FakeScreen.waiting_for_name)
    await message.answer("Введи имя клиента (будет в шапке чата):")

@dp.message(FakeScreen.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    name = message.text.strip()
    if len(name) > 25:
        await message.answer("Имя слишком длинное (макс. 25 символов). Попробуй ещё раз.")
        return
    await state.update_data(name=name)
    await state.set_state(FakeScreen.waiting_for_review)
    await message.answer("Теперь напиши текст отзыва (последнее сообщение):")

@dp.message(FakeScreen.waiting_for_review)
async def process_review(message: types.Message, state: FSMContext):
    review = message.text.strip()
    data = await state.get_data()
    name = data["name"]

    await message.answer("⏳ Генерирую скриншот...")
    img_path = await generate_fake_screen(name, review)

    photo = types.FSInputFile(img_path)
    await message.answer_photo(photo, caption="✅ Готово!")
    await state.clear()
    os.remove(img_path)

@dp.message(Command("cancel"))
async def cancel_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Действие отменено.")

# ---------- Запуск ----------
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
