# Bot ekonomii serwera Discord

Projekt jest botem ekonomii serwera napisanym w Pythonie z użyciem biblioteki `discord.py`. Bot obsługuje konto użytkownika, historię aktywności, statystyki, przekazywanie respektu, doładowania oraz proste gry losowe. Liczby losowe mogą być pobierane przez kolejkę RabbitMQ.

Interfejs wiadomości został wykonany za pomocą `discord.ui.LayoutView`, `discord.ui.Container`, `discord.ui.TextDisplay`, `discord.ui.Separator` oraz `discord.ui.ActionRow`. Dzięki temu wiadomości są czytelne i dobrze wyglądają na Discordzie.

## Funkcje projektu

- obsługa komend slash Discorda,
- system kont użytkowników,
- punkty ekonomii serwera nazwane `respekt`,
- zapis danych w bazie SQLite,
- historia ostatnich aktywności,
- statystyki użytkownika,
- przekazywanie respektu między użytkownikami,
- doładowanie konta przez panel WWW,
- 6-cyfrowy kod wysyłany użytkownikowi w wiadomości prywatnej na Discordzie,
- konfigurowalne wyciszenie użytkownika po doładowaniu,
- gra `losowanie`,
- gra `multi_losowanie`,
- gra `kolory`,
- gra `karty`,
- pobieranie liczb losowych przez RabbitMQ,
- pobieranie paczek liczb z zewnętrznego API,
- osobny plik z tokenem bota,
- podstawowy panel WWW uruchamiany lokalnie.

## Technologie

Projekt wykorzystuje:

- Python 3,
- discord.py,
- aiohttp,
- aiosqlite,
- aio-pika,
- Flask,
- SQLite,
- RabbitMQ,
- Docker do uruchamiania RabbitMQ.

## Struktura projektu

```text
Bot/
├── bot.py
├── config.json
├── token.json
├── requirements.txt
├── cogs/
│   ├── cards_cog.py
│   ├── colors_cog.py
│   ├── drawing_cog.py
│   └── economy_cog.py
├── games/
│   ├── cards_game.py
│   ├── colors_game.py
│   └── drawing_game.py
├── services/
│   ├── database.py
│   ├── random_queue.py
│   └── web_panel.py
└── views/
    ├── card_view.py
    ├── transfer_view.py
    └── stats_view.py
```

## Instalacja

Najpierw pobierz projekt i przejdź do folderu z botem.

```bash
git clone LINK_DO_REPOZYTORIUM
cd NAZWA_FOLDERU
```

Utwórz środowisko wirtualne.

```bash
python -m venv venv
```

Aktywuj środowisko.

Na Windows:

```bash
venv\Scripts\activate
```

Na macOS albo Linux:

```bash
source venv/bin/activate
```

Zainstaluj wymagane biblioteki.

```bash
pip install -r requirements.txt
```

## Konfiguracja bota

Projekt ma dwa osobne pliki konfiguracyjne:

```text
config.json
```

oraz:

```text
token.json
```

Plik `config.json` przechowuje ustawienia bota, na przykład początkowy stan konta, nazwę punktów ekonomii, koszt rund, ustawienia bazy danych, ustawienia doładowania i RabbitMQ.

Przykład:

```json
{
  "bot_settings": {
    "prefix": "!",
    "default_balance": 1000
  },
  "economy_settings": {
    "currency_name": "respekt",
    "currency_name_genitive": "respektu",
    "currency_icon": "⭐"
  },
  "files": {
    "database": "economy.db",
    "log_file": "economy_bot.log"
  },
  "drawing_settings": {
    "default_entry_cost": 10,
    "multiplier": 1.5,
    "success_rate": 0.2,
    "multi_success_rate": 0.2,
    "bonus_success_rate": 0.2
  },
  "colors_settings": {
    "default_entry_cost": 10,
    "success_rate": 0.2
  },
  "topup_settings": {
    "expiry_time_token": 15,
    "mute_enabled": true,
    "mute_points_unit": 100,
    "mute_seconds_per_unit": 30,
    "guild_id": 0,
    "reason": "Doładowanie respektu przez panel ekonomii"
  },
  "random_queue": {
    "enabled": true,
    "rabbitmq_url": "amqp://guest:guest@127.0.0.1:5672/",
    "queue_name": "economy_random_numbers",
    "batch_size": 30,
    "min_value": 1,
    "max_value": 1000,
    "api_url": "https://www.random.org/integers/?num={count}&min={min_value}&max={max_value}&col=1&base=10&format=plain&rnd=new"
  }
}
```

W sekcji `topup_settings` można ustawić przelicznik wyciszenia po doładowaniu:

```json
"mute_enabled": true,
"mute_points_unit": 100,
"mute_seconds_per_unit": 30,
"guild_id": 0
```

Przy takim ustawieniu każde 100 respektu daje 30 sekund wyciszenia. Przykładowo 1000 respektu daje 300 sekund, czyli 5 minut. W polu `guild_id` trzeba wpisać ID serwera Discord. Jeżeli zostanie `0`, bot doda respekt, ale nie będzie miał konkretnego serwera do nadania wyciszenia.

Plik `token.json` przechowuje tylko token bota Discord.

```json
{
  "token": "WKLEJ_TUTAJ_TOKEN_BOTA"
}
```

Token nie powinien być wrzucany na GitHuba. Z tego powodu plik `token.json` powinien być dodany do `.gitignore`.

## Uruchomienie RabbitMQ

Do pobierania liczb losowych używana jest kolejka RabbitMQ. Najprościej uruchomić ją przez Dockera.

```bash
docker run -d --name rabbitmq-economy -p 5672:5672 -p 15672:15672 rabbitmq:3-management
```

Panel RabbitMQ będzie dostępny pod adresem:

```text
http://localhost:15672
```

Dane logowania:

```text
login: guest
hasło: guest
```

Kolejka z liczbami powinna mieć nazwę:

```text
economy_random_numbers
```

## Jak działa losowanie liczb

Losowanie liczb działa przez RabbitMQ. Bot nie musi pobierać każdej liczby osobno bezpośrednio w rundzie. Zamiast tego pobiera paczkę liczb z API i zapisuje je w kolejce.

Schemat działania:

```text
API random.org
      ↓
paczka 30 liczb
      ↓
RabbitMQ
      ↓
gry: losowanie, multi_losowanie, kolory, karty
```

Gdy gra potrzebuje liczby losowej, pobiera ją z kolejki. Jeśli kolejka jest pusta, bot pobiera kolejną paczkę liczb z API i uzupełnia kolejkę.

Jeżeli RabbitMQ albo API chwilowo nie działa, bot korzysta z awaryjnego losowania lokalnego, żeby runda mogła zostać dokończona.

## Uruchomienie bota

Po skonfigurowaniu plików `config.json` i `token.json` uruchom bota komendą:

```bash
python bot.py
```

Po poprawnym starcie w terminalu powinny pojawić się logi informujące o załadowaniu cogów oraz połączeniu z RabbitMQ.

## Komendy bota

Bot obsługuje następujące komendy slash:

| Komenda | Opis |
|---|---|
| `/konto` | Pokazuje aktualny stan konta użytkownika. |
| `/historia` | Pokazuje ostatnie aktywności użytkownika. |
| `/statystyki` | Pokazuje statystyki użytkownika. |
| `/przelej` | Pozwala przekazać respekt innemu użytkownikowi. |
| `/doladuj` | Doładowuje konto użytkownika. |
| `/pomoc` | Pokazuje listę komend. |
| `/losowanie` | Uruchamia klasyczne losowanie. |
| `/multi_losowanie` | Uruchamia kilka losowań obok siebie. |
| `/kolory` | Uruchamia grę z wyborem koloru. |
| `/karty` | Uruchamia grę w karty. |

## Gry losowe

### Losowanie

Gra polega na wylosowaniu symboli. Koszt rundy jest odejmowany na początku, a ewentualna nagroda jest dodawana po zakończeniu rundy.

### Multi losowanie

Tryb `multi_losowanie` uruchamia kilka losowań jednocześnie. Wynik zależy od wylosowanych symboli oraz ustawień z pliku `config.json`.

### Kolory

Gra `kolory` pozwala wybrać kolor: czerwony, czarny albo zielony. Wynik jest wyświetlany w widoku wykonanym przy pomocy komponentów Discorda.

### Karty

Gra `karty` pozwala grać przeciwko botowi. Użytkownik może dobierać karty albo zostać przy aktualnym wyniku. Karty są wybierane na podstawie liczb pobieranych z kolejki RabbitMQ.

## Baza danych

Projekt używa bazy SQLite. Domyślna nazwa pliku bazy to:

```text
economy.db
```

W bazie przechowywane są między innymi:

- stan kont użytkowników,
- historia aktywności,
- statystyki aktywności,
- kody potrzebne do doładowania konta.

Ustawienia szans i kosztów są pobierane z pliku `config.json`.

## Panel WWW

Projekt zawiera prosty panel WWW oparty o Flask. Panel jest uruchamiany razem z botem, jeśli plik `services/web_panel.py` jest dostępny.

Domyślnie panel działa lokalnie na porcie:

```text
5000
```

Adres lokalny:

```text
http://localhost:5000
```

Po użyciu komendy `/doladuj` bot generuje link i wysyła użytkownikowi 6-cyfrowy kod w wiadomości prywatnej. Kod trzeba przepisać w panelu WWW. Po zatwierdzeniu użytkownik dostaje wpisaną ilość respektu. Jeżeli w `config.json` włączono `mute_enabled`, bot wylicza czas wyciszenia z przelicznika `mute_points_unit` i `mute_seconds_per_unit`.

## Pliki, których nie należy wrzucać na GitHuba

Na GitHuba nie powinno się wrzucać plików zawierających dane prywatne albo plików generowanych automatycznie.

Przykładowy `.gitignore`:

```gitignore
__pycache__/
*.pyc
venv/
.env
token.json
economy.db
economy_bot.log
```

Najważniejsze jest to, żeby nie publikować pliku `token.json`, ponieważ zawiera token bota Discord.

## Najczęstsze problemy

### Kolejka RabbitMQ nie pojawia się w panelu

Sprawdź, czy RabbitMQ działa.

```bash
docker ps
```

Sprawdź też, czy bot został uruchomiony i czy w terminalu nie ma błędu połączenia z RabbitMQ.

### Bot nie startuje

Sprawdź, czy istnieją pliki:

```text
config.json
token.json
```

Sprawdź też, czy w `token.json` jest prawdziwy token bota.

### Komendy slash nie są widoczne na Discordzie

Po pierwszym uruchomieniu synchronizacja komend może chwilę potrwać. Warto też sprawdzić, czy bot został zaproszony na serwer z odpowiednimi uprawnieniami.

### Wyciszenie po doładowaniu nie działa

Sprawdź, czy w `config.json` ustawiono prawidłowe `guild_id`. Bot musi być na tym serwerze i musi mieć uprawnienie do wyciszania użytkowników.

### Błąd z bibliotekami

Zainstaluj ponownie zależności.

```bash
pip install -r requirements.txt
```

## Autor

Projekt wykonany jako bot ekonomii serwera Discord z obsługą gier losowych, kont użytkowników, statystyk oraz kolejki RabbitMQ do pobierania liczb losowych.
