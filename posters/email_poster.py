"""
    Модуль email_poster.py

    Данный модуль определяет классы для отправки уведомлений по электронной почте
    в рамках системы мониторинга. Предназначен для интеграции с очередью сообщений,
    генерации писем на основе содержимого сообщений и отправки их через SMTP-сервер.

    Классы:
    --------
    - EmailPoster: Реализация постера, которая получает сообщения из очереди,
      определяет тему письма (на основе ключевых слов "url" или "Proxmox"),
      генерирует письма с помощью EmailGenerator и отправляет их через EmailSender.
    - EmailGenerator: Генератор списка Email-объектов для указанных получателей.
    - EmailSender: Отправитель писем через SMTP-сервер с использованием SSL.

    Ключевые зависимости:
    -----------------------
    - smtplib: для отправки писем по протоколу SMTP
    - ssl: для создрания защищенного контекста
    - email.mime: для формирования mime-сообщений
    - dataclasses: для определения структуры Email
    - posters.poster.Poster: базовый класс постера

    Пример использования:
    -----------------------
    # Создание очереди и постера
    result_queue = queue.Queue()
    poster = EmailPoster(result_queue, config)

    # В отдельном потоке запускаем постер
    threading.Thread(target=poster.run, daemon=True).start()

    # Помещаем сообщение в очередь
    result_queue.put("Изменение статуса url сайта: https://example.com")

"""
from posters.poster import Poster
import queue

import smtplib
import ssl

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from dataclasses import dataclass

from typing import List


from typing import Dict, Any


@dataclass
class Email:
    """
    Датакласс, представляющий одно электронное письмо.

    Attributes:
        subject (str): Тема письма.
        body (str): Текст письма.
        from_email (str): Адрес отправителя.
        to_email (str): Адрес получателя.
    """
    subject: str
    body: str
    from_email: str
    to_email: str


class EmailPoster(Poster):
    """
    Постер для отправки уведомлений по электронной почте.

    Кратко:
        Получает сообщения из очереди, определяет тему письма на основе ключевых слов
        ("url" -> HTTP-робот, "Proxmox" -> PM-робот, иначе общая тема), генерирует
        письма для всех адресов из конфигурации и отправляет их через EmailSender.

    Args:
        result_queue (queue.Queue): Очередь сообщений для обработки.
        config (Dict[str, Any]): Конфигурация SMTP и получателей. Должна содержать
            ключи: "LOGIN", "PASSWORD", "SMTP_SERVER", "SMTP_PORT", "TO_EMAILS".

    Attributes:
        result_queue (queue.Queue): Сохранённая очередь.
        config (Dict[str, Any]): Сохранённая конфигурация.

    Public methods:
        run() -> None:
            Бесконечный цикл: извлекает сообщение из очереди, определяет тему,
            генерирует письма и отправляет их. При пустой очереди продолжает ожидание.

    Behavior notes:
        - При получении сообщения, содержащего подстроку "url", тема письма устанавливается как
          "[HTTP-робот] Изменение статуса url сайта".
        - При содержании "Proxmox" тема — "[PM-робот] Изменение статуса ВМ в Proxmox".
        - Иначе тема — "Изменение статуса".
        - Письма генерируются для всех адресов из config["TO_EMAILS"] с использованием
          EmailGenerator, после чего отправляются через EmailSender.
        - Исключение queue.Empty игнорируется (очередь пуста, цикл продолжается).
    """
    def __init__(self, result_queue: queue.Queue, config: Dict[str, Any]):
        """
        Инициализирует постер с очередью и конфигурацией.

        Args: 
            result_queue (queue.Queue): Очередь сообщений для отправки.
            config (Dict[str, Any]): Конфигурация.
        """
        self.result_queue = result_queue
        self.config = config

    def run(self):
        """
        Запускает бесконечный цикл обработки сообщений из очереди.

        Каждое сообщение обрабатывается:
            1. Извлекается из очереди (блокирующее ожидание).
            2. Выбирается префикс в зависимости от содержимого.
            3. Генерирутеся письмо в EmailGenerator с логином из config["LOGIN"].
            4. Сгенерированное письмо отправляется с помощью EmailSender.

        Если в очереди нет сообщений, цикл продолжается с небольшой задержкой
        (queue.get блокирует поток, но при queue.Empty не блокируется).
        """
        while True:
            try:
                body = self.result_queue.get()
                if "url" in body:
                    subject = "[HTTP-робот] Изменение статуса url сайта"
                elif "Proxmox" in body:
                    subject = "[PM-робот] Изменение статуса ВМ в Proxmox"
                else:
                    subject = "Изменение статуса"

                emails = EmailGenerator(self.config["LOGIN"], self.config["TO_EMAILS"]).generate_email(subject=subject, body=body)
                EmailSender(emails=emails, smtp_config=self.config).send_emails()
            except queue.Empty:
                continue


class EmailGenerator:
    """
    Генератор писем на основе списка получателей.

    Кратко: 
        Создает список объектов Email для указанных получателей,
        используя общую тему и тело.

    Args:
        from_email (str): Адрес отправителя
        to_emails (List[str]): Список адресов получателей.

    Public methods:
        generate_email(subject: str, body: str) -> List[Email]:
            Генерирует список писем для всех получателей, используя заданную тему и тело
    """
    def __init__(self, from_email: str, to_emails: List[str]):
        """
        Инициализирует генератор с адресом отправителя и списком адресов получателей.
        Args:
            from_email (str): Адрес отправителя
            to_emails (List[str]): Список адресов получателей.
        """
        self.from_email = from_email
        self.to_emails = to_emails

    def generate_email(self, subject: str, body: str) -> List[Email]:
        """
        Генерирует список писем на основе заданных параметров.

        Args:
            subject (str): Тема письма.
            body (str): Текст письма.
        Returns:
            List[Email]: Список сгенерированных писем.
        """
        emails = []
        for to_email in self.to_emails:
            email = Email(
                subject=subject,
                body=body,
                from_email=self.from_email,
                to_email=to_email,
            )
            emails.append(email)
        return emails


class EmailSender:
    """
    Отправитель писем через SMTP-сервер.

    Кратко:
        Отправляет переданные письма, используя конфигурацию SMTP (сервер, порт, логин, пароль)
        Соединение устанавливается отдельно для каждого письма (в текущей реализации).

    Args:
        emails (List[Email]): Список писем для отправки.
        smtp_config (Dict[str, Any]):  Конфигурация SMTP, содержащая ключи:
            "SMTP_SERVER", "SMTP_PORT", "LOGIN", "PASSWORD".

    Public methods:
        send_emails() -> List[bytes]:
            Отправляет все письма, возвращается список байтовых представлений отправленных сообщений
    
    
    """
    def __init__(self, emails: List[Email], smtp_config: Dict[str, Any]):
        self.emails = emails
        self.smtp_config = smtp_config

    def send_emails(self):
        """
        Отправляет все сгенерированные письма.
        """
        sent_messages = []

        for email_data in self.emails:
            
            msg = MIMEMultipart()
            msg["From"] = email_data.from_email
            msg["To"] = email_data.to_email
            msg["Subject"] = email_data.subject
            # Тело письма
            msg.attach(MIMEText(email_data.body, "plain", "utf-8"))

            # Отправка через SMTP
            context = ssl.create_default_context()
            server = smtplib.SMTP_SSL(
                self.smtp_config["SMTP_SERVER"],
                int(self.smtp_config["SMTP_PORT"]),
                context=context
            )
            server.login(self.smtp_config["LOGIN"], self.smtp_config["PASSWORD"])
            text = msg.as_string()
            server.sendmail(email_data.from_email, email_data.to_email, text)
            server.quit()

            msg_bytes = msg.as_bytes()
            sent_messages.append(msg_bytes)

        return sent_messages