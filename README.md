# Bot kasynowy Discord

Bot kasynowy napisany w Pythonie z użyciem biblioteki `discord.py`. Projekt obsługuje gry kasynowe, saldo użytkownika, historię gier, statystyki, przelewy monet, doładowania oraz losowanie liczb przez kolejkę RabbitMQ.

Interfejs wiadomości został wykonany za pomocą `discord.ui.LayoutView`, `discord.ui.Container`, `discord.ui.TextDisplay`, `discord.ui.Separator` oraz `discord.ui.ActionRow`. Dzięki temu wiadomości wyglądają podobnie do embedów, ale nie są klasycznymi `discord.Embed`.

## Funkcje projektu

- obsługa komend slash Discorda,
- system salda użytkowników,
- zapis danych w bazie SQLite,
- historia ostatnich gier,
- statystyki gracza,
- przelewanie monet między graczami,
- doładowanie konta,
- gra w sloty,
- gra w multi sloty,
- gra w ruletkę,
- gra w blackjacka,
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
├── config.example.json
├── token.json
├── token.example.json
├── requirements.txt
├── cogs/
│   ├── blackjack_cog.py
│   ├── casino_cog.py
│   ├── roulette_cog.py
│   └── slots_cog.py
├── games/
│   ├── blackjack.py
│   ├── roulette.py
│   └── slot_machine.py
├── services/
│   ├── database.py
│   ├── random_queue.py
│   └── web_panel.py
└── views/
    ├── card_view.py
    ├── pay_view.py
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

Plik `config.json` przechowuje zwykłe ustawienia bota, na przykład domyślne saldo, stawki, szanse na wygraną, ustawienia bazy danych i RabbitMQ.

Przykład:

```json
{
  "bot_settings": {
    "prefix": "!",
    "default_balance": 1000
  },
  "files": {
    "database": "casino.db",
    "log_file": "casino_games.log"
  },
  "slots_settings": {
    "default_bet": 10,
    "multiplier": 1.5,
    "win_rate": 0.2,
    "multi_win_rate": 0.2,
    "bonus_win_rate": 0.2
  },
  "roulette_settings": {
    "default_bet": 10,
    "win_rate": 0.2
  },
  "payments": {
    "expiry_time_token": 15
  },
  "random_queue": {
    "enabled": true,
    "rabbitmq_url": "amqp://guest:guest@127.0.0.1:5672/",
    "queue_name": "casino_random_numbers",
    "batch_size": 30,
    "min_value": 1,
    "max_value": 1000,
    "api_url": "https://www.random.org/integers/?num={count}&min={min_value}&max={max_value}&col=1&base=10&format=plain&rnd=new"
  }
}
```

Plik `token.json` przechowuje tylko token bota Discord.

```json
{
  "token": "WKLEJ_TUTAJ_TOKEN_BOTA"
}
```

Token nie powinien być wrzucany na GitHuba. Z tego powodu plik `token.json` powinien być dodany do `.gitignore`.

## Uruchomienie RabbitMQ

Do losowania liczb używana jest kolejka RabbitMQ. Najprościej uruchomić ją przez Dockera.

```bash
docker run -d --name rabbitmq-casino -p 5672:5672 -p 15672:15672 rabbitmq:3-management
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
casino_random_numbers
```

## Jak działa losowanie liczb

Losowanie liczb działa przez RabbitMQ. Bot nie musi pobierać każdej liczby osobno bezpośrednio w grze. Zamiast tego pobiera paczkę liczb z API i zapisuje je w kolejce.

Schemat działania:

```text
API random.org
      ↓
paczka 30 liczb
      ↓
RabbitMQ
      ↓
gry: sloty, ruletka, blackjack
```

Gdy gra potrzebuje liczby losowej, pobiera ją z kolejki. Jeśli kolejka jest pusta, bot pobiera kolejną paczkę liczb z API i uzupełnia kolejkę.

Jeżeli RabbitMQ albo API chwilowo nie działa, bot korzysta z awaryjnego losowania lokalnego, żeby gra nie przerwała działania.

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
| `/balance` | Pokazuje aktualne saldo użytkownika. |
| `/historia` | Pokazuje ostatnie gry użytkownika. |
| `/stats` | Pokazuje statystyki gracza. |
| `/pay` | Pozwala przelać monety innemu graczowi. |
| `/doladuj` | Doładowuje konto użytkownika. |
| `/help` | Pokazuje listę komend. |
| `/slots` | Uruchamia automat do gry. |
| `/multi_slots` | Uruchamia kilka automatów obok siebie. |
| `/ruletka` | Uruchamia ruletkę z wyborem koloru. |
| `/blackjack` | Uruchamia grę w blackjacka. |

## Gry

### Sloty

Gra polega na wylosowaniu symboli na automacie. Stawka jest odejmowana na początku gry, a ewentualna wygrana jest dodawana po zakończeniu rundy.

### Multi sloty

Tryb multi slotów uruchamia kilka automatów jednocześnie. Wynik zależy od wylosowanych symboli oraz ustawień z pliku `config.json`.

### Ruletka

Ruletka pozwala wybrać kolor, na który gracz chce postawić monety. Dostępne są przyciski wyboru koloru. Wynik jest wyświetlany w widoku wykonanym przy pomocy komponentów Discorda.

### Blackjack

Blackjack pozwala grać przeciwko krupierowi. Gracz może dobierać karty albo zatrzymać aktualną rękę. Karty są wybierane na podstawie liczb pobieranych z kolejki RabbitMQ.

## Baza danych

Projekt używa bazy SQLite. Domyślna nazwa pliku bazy to:

```text
casino.db
```

W bazie przechowywane są między innymi:

- saldo graczy,
- historia gier,
- statystyki gier,
- informacje potrzebne do działania systemu kasyna.

Szanse na wygraną nie są przechowywane w bazie danych. Są pobierane z pliku `config.json`.

## Panel WWW

Projekt zawiera prosty panel WWW oparty o Flask. Panel jest uruchamiany razem z botem, jeśli moduł `services/web_panel.py` jest dostępny.

Domyślnie panel działa lokalnie na porcie:

```text
5000
```

Adres lokalny:

```text
http://localhost:5000
```

## Pliki, których nie należy wrzucać na GitHuba

Na GitHuba nie powinno się wrzucać plików zawierających dane prywatne albo plików generowanych automatycznie.

Przykładowy `.gitignore`:

```gitignore
__pycache__/
*.pyc
venv/
.env
token.json
casino.db
casino_games.log
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

### Błąd z bibliotekami

Zainstaluj ponownie zależności.

```bash
pip install -r requirements.txt
```

## Autor

Projekt wykonany jako bot kasynowy Discord z obsługą gier, salda, statystyk oraz kolejki RabbitMQ do pobierania liczb losowych.
