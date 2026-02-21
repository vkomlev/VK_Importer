"""Единый реестр типов курсов и маппинг канал → генератор заголовков (Phase 2)."""

# Типы курсов для маппинга папка → курс (folders set/list в CLI)
COURSE_TYPES = ("Python", "ЕГЭ", "ОГЭ", "Алгоритмы", "Excel", "Комлев", "Аналитика данных")

# Канал (название курса) → имя генератора заголовков (TitleGeneratorFactory)
# Используется в scanner и в CLI (recalc-titles, upload фильтры)
CHANNEL_TO_TITLE_GENERATOR = {
    "ЕГЭ": "ege_auto",
    "ОГЭ": "oge_auto",
    "Алгоритмы": "algorithms_auto",
    "Python": "python_auto",
    "Excel": "excel",
    "Аналитика данных": "analytics",
    "Комлев": "komlev",
}
