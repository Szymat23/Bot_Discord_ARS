import asyncio
import logging
import json
import random
import re
from typing import List, Optional

import aiohttp

try:
    import aio_pika
except ImportError:  # zabezpieczenie, gdy ktoś nie zainstalował requirements.txt
    aio_pika = None

logger = logging.getLogger("CasinoBot")


class RandomQueueService:
    def __init__(self, config: dict):
        queue_config = config.get("random_queue", {})

        self.enabled = queue_config.get("enabled", True)
        self.rabbitmq_url = queue_config.get("rabbitmq_url", "amqp://guest:guest@localhost/")
        self.queue_name = queue_config.get("queue_name", "casino_random_numbers")
        self.batch_size = int(queue_config.get("batch_size", 30))
        self.min_value = int(queue_config.get("min_value", 1))
        self.max_value = int(queue_config.get("max_value", 1000))
        self.api_url = queue_config.get(
            "api_url",
            "https://www.randomnumberapi.com/api/v1.0/random?min={min_value}&max={max_value}&count={count}"
        )

        self.connection = None
        self.channel = None
        self.queue = None
        self.lock = asyncio.Lock()

    async def connect(self) -> bool:
        if not self.enabled:
            logger.info("RANDOM_QUEUE | Kolejka liczb jest wyłączona w configu.")
            return False

        if aio_pika is None:
            logger.warning("RANDOM_QUEUE | Brak biblioteki aio-pika. Używane będzie losowanie awaryjne.")
            return False

        if self.connection and not self.connection.is_closed:
            return True

        try:
            self.connection = await aio_pika.connect_robust(self.rabbitmq_url, timeout=5)
            self.channel = await self.connection.channel()
            self.queue = await self.channel.declare_queue(self.queue_name, durable=True)
            logger.info("RANDOM_QUEUE | Połączono z RabbitMQ. Kolejka: %s", self.queue_name)
            await self.refill_queue()
            return True
        except Exception as exc:
            logger.warning("RANDOM_QUEUE | Nie udało się połączyć z RabbitMQ: %s", exc)
            self.connection = None
            self.channel = None
            self.queue = None
            return False

    def build_api_url(self) -> str:
        return self.api_url.format(
            min_value=self.min_value,
            max_value=self.max_value,
            count=self.batch_size
        )

    def parse_numbers(self, body: str, content_type: str = "") -> List[int]:
        numbers: List[int] = []
        body = body.strip()

        if not body:
            return numbers

        try:
            if "json" in content_type.lower() or body.startswith("["):
                data = json.loads(body)
                numbers = [int(number) for number in data]
            else:
                raw_numbers = re.findall(r"-?\d+", body)
                numbers = [int(number) for number in raw_numbers]
        except Exception as exc:
            logger.warning("RANDOM_QUEUE | Nie udało się odczytać liczb z odpowiedzi API: %s", exc)
            return []

        numbers = [
            number
            for number in numbers
            if self.min_value <= number <= self.max_value
        ]

        return numbers

    async def fetch_numbers_from_api(self) -> List[int]:
        url = self.build_api_url()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    body = await response.text()

                    if response.status != 200:
                        logger.warning("RANDOM_QUEUE | API zwróciło status: %s", response.status)
                        logger.warning("RANDOM_QUEUE | Odpowiedź API: %s", body[:200].replace("\n", " "))
                        return []

                    content_type = response.headers.get("Content-Type", "")
                    numbers = self.parse_numbers(body, content_type)

                    if not numbers:
                        logger.warning("RANDOM_QUEUE | API nie zwróciło żadnych liczb. Odpowiedź: %s", body[:200].replace("\n", " "))
                        return []

                    logger.info("RANDOM_QUEUE | Pobrano %s liczb z API.", len(numbers))
                    return numbers
        except Exception as exc:
            logger.warning("RANDOM_QUEUE | Nie udało się pobrać liczb z API: %s", exc)
            return []

    async def refill_queue(self) -> int:
        if not await self.connect_if_needed():
            return 0

        numbers = await self.fetch_numbers_from_api()
        if not numbers:
            return 0

        try:
            for number in numbers:
                message = aio_pika.Message(
                    body=str(number).encode("utf-8"),
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT
                )
                await self.channel.default_exchange.publish(
                    message,
                    routing_key=self.queue_name
                )

            logger.info("RANDOM_QUEUE | Dodano %s liczb do kolejki.", len(numbers))
            return len(numbers)
        except Exception as exc:
            logger.warning("RANDOM_QUEUE | Nie udało się dodać liczb do kolejki: %s", exc)
            return 0

    async def connect_if_needed(self) -> bool:
        if not self.enabled:
            return False

        if aio_pika is None:
            return False

        if self.connection and not self.connection.is_closed and self.queue:
            return True

        try:
            self.connection = await aio_pika.connect_robust(self.rabbitmq_url, timeout=5)
            self.channel = await self.connection.channel()
            self.queue = await self.channel.declare_queue(self.queue_name, durable=True)
            return True
        except Exception as exc:
            logger.warning("RANDOM_QUEUE | RabbitMQ jest niedostępny: %s", exc)
            self.connection = None
            self.channel = None
            self.queue = None
            return False

    async def get_number(self) -> int:
        async with self.lock:
            if await self.connect_if_needed():
                number = await self.get_number_from_queue()
                if number is not None:
                    return number

                await self.refill_queue()
                number = await self.get_number_from_queue()
                if number is not None:
                    return number

            fallback = random.randint(self.min_value, self.max_value)
            logger.warning("RANDOM_QUEUE | Użyto awaryjnego losowania lokalnego: %s", fallback)
            return fallback

    async def get_number_from_queue(self) -> Optional[int]:
        if not self.queue:
            return None

        try:
            message = await self.queue.get(no_ack=False, fail=False, timeout=2)
            if message is None:
                return None

            async with message.process():
                return int(message.body.decode("utf-8"))
        except Exception as exc:
            logger.warning("RANDOM_QUEUE | Nie udało się pobrać liczby z kolejki: %s", exc)
            return None

    async def close(self):
        try:
            if self.connection and not self.connection.is_closed:
                await self.connection.close()
        except Exception as exc:
            logger.warning("RANDOM_QUEUE | Błąd podczas zamykania połączenia: %s", exc)
