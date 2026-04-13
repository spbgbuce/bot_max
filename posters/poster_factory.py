"""
    Модуль poster_factory.py

    Данный модуль определяет фабрику для создания объектов-постеров,
    которые отвечают за отправку сообщений (например, в чаты ботов, по email и т.д.).
    Фабрика скрывает детали создания конкретных постеров и возвращает экземпляр,
    реализующий интерфейс Poster. Это позволяет гибко переключаться между различными
    способами доставки сообщений без изменения вызывающего кода.

    Классы:
    --------
    - PosterFactory: Фабричный класс, создающий постеры по типу.
      Содержит статический метод create_poster, который по строковому идентификатору
      возвращает нужный объект.

    Ключевые зависимости:
    ----------------------
    - posters.poster.Poster: Абстрактный базовый класс для всех постеров.
    - posters.email_poster.BotMaxPoster: Конкретная реализация постера для отправки
      сообщений через Max бота.

    Пример использования:
    ----------------------
    result_queue = queue.Queue()
    poster = PosterFactory.create_poster("bot_max", result_queue)
    # Запуск постера в отдельном потоке
    threading.Thread(target=poster.run, daemon=True).start()
"""

from posters.poster import Poster
from posters.email_poster import EmailPoster
from posters.bot_max_poster import BotMaxPoster
from typing import Dict, Any
import queue


class PosterFactory:
    """
    Фабрика для создания объектов-постеров.

    Кратко:
        Предоставляет статический метод create_poster, который по заданному типу
        создаёт и возвращает экземпляр соответствующего постера. Фабрика скрывает
        логику инициализации и зависимости конкретных реализаций.

    Public methods:
        create_poster(poster_type: str, result_queue: queue.Queue, **kwargs) -> Poster:
            Создаёт постер указанного типа с переданной очередью и дополнительными
            параметрами. Возвращает объект, реализующий интерфейс Poster.

    Raises:
        ValueError: если передан неизвестный тип постера.

    Пример использования:
        factory = PosterFactory()
        poster = factory.create_poster("bot_max", queue.Queue())
        poster.run()
    """
    @staticmethod
    def create_poster(poster_type: str, result_queue: queue.Queue, config: Dict[str, Any], **kwargs) -> Poster:
        """
        Создаёт постер указанного типа.

        Аргументы:
            poster_type (str): Тип постера. Поддерживаемые значения:
                - "bot_max" – постер для отправки сообщений через Max бота.
            result_queue (queue.Queue): Очередь, из которой постер будет получать
                сообщения для отправки.
            **kwargs: Дополнительные параметры, специфичные для конкретного постера
                (в текущей реализации не используются, но могут быть добавлены в будущем).

        Возвращаемое значение:
            Poster: Экземпляр постера, реализующий интерфейс Poster.

        Raises:
            ValueError: Если poster_type не поддерживается.

        Пример:
            queue = queue.Queue()
            poster = PosterFactory.create_poster("bot_max", queue)
            # ... в другом потоке
            queue.put("Сообщение")
            poster.run()  # отправляет сообщение
        """
        if poster_type == "bot_max":
            return BotMaxPoster(result_queue, config=config)
        elif poster_type == "email":
            return EmailPoster(result_queue=result_queue, config=config)
        else:
            raise ValueError(f"Неизвестный тип постера: {poster_type}")
