# GHOSTMAP

Нативное приложение на Python / PySide6 для проектов разрешённого пентеста.
MVP: проекты SQLite, Host / Service / Finding / Credential-reference / Access / Note,
ручные связи, Nmap, потоковый импорт XML, интерактивная карта, история сканирований.
Постоянный сервер и браузер не используются. Credential — только ссылка на внешний
менеджер секретов; пароли и токены в базу вводить не следует.

## Kali / Debian

```sh
sudo apt update
sudo apt install python3 python3-pyside6.qtcore python3-pyside6.qtgui python3-pyside6.qtwidgets nmap
python3 scripts/build_deb.py
sudo apt install ./dist/ghostmap_0.1.0_all.deb
ghostmap
```

Пакет содержит только собственный код, SVG и launcher. Python, Qt и Nmap берутся
из системных пакетов. Перед установкой проверьте `apt install --simulate` и
`apt-cache show` — размер зависимостей зависит от уже установленной системы.
Удаление: `sudo apt remove ghostmap`. Пользовательские проекты при удалении
сохраняются; удалить их отдельно можно из каталога данных GHOSTMAP.

## Запуск из исходников

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m ghostmap
```

В Kali с установленными системными зависимостями достаточно `python3 -m ghostmap`.
Для Debian wheel может потребовать `libegl1`, `libopengl0` и зависимости xcb.
`requirements-dev.txt` включает только Qt Essentials — дополнительные Qt-модули
не нужны. Для реальных сканирований Nmap должен находиться в PATH.

## Рабочий процесс

1. Создайте проект, добавьте разрешённый IP и выберите Quick.
2. Подтвердите разрешение и запустите Nmap. По умолчанию работает один сканер;
   Full / Service Enumeration / Custom требуют подтверждения нагрузки.
3. После успешного завершения XML автоматически создаёт хосты и открытые сервисы.
4. Колёсико — zoom; средняя кнопка — pan; левая кнопка — drag узла.
   Ctrl+click или рамка выбирают несколько узлов; Link создаёт направленную связь.
5. Arrange размещает отображаемую страницу по типам. Координаты сохраняются при
   отпускании узла. Ctrl+0 — вписать карту, Ctrl+F — поиск, Ctrl+S — сохранить заметки.
6. В инспекторе можно сохранить доказательства и статус hypothesis / confirmed.
   Пунктир обозначает гипотезу. Note nodes сохраняются вместе с картой.

Данные: `QStandardPaths.AppDataLocation` (обычно `~/.local/share/GHOSTMAP/GHOSTMAP`);
настройки панелей — QSettings. Можно указать `--database /path/project.sqlite3`.
Исходный XML создаётся в приватном временном каталоге и удаляется после импорта.
Логи ограничены 600 строками и 100 000 символами; история — последние 100 задач. Карта загружает
страницу до 400 объектов; видны связи только между объектами текущей страницы.
Фильтр типа применяется к текущей странице. Неоконченные задачи после перезапуска
помечаются interrupted. Закрытие во время сканирования или импорта предотвращается.

## Проверки

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -v
```

Тесты проверяют SQLite, атомарный импорт XML, сохранение заметок при повторном
импорте, реальные QProcess/Nmap на loopback, восстановление карты, события
zoom/pan/drag и ограничение логов. Пакет проверяется отдельным скриптом
`python3 scripts/check_package.py` в подготовленной облачной среде. Nmap-test пропускается,
если Nmap отсутствует: это не является подтверждением работоспособности сканера.

## Границы MVP

Поддерживается один IPv4/IPv6 адрес за сканирование; диапазоны и домены,
WhatWeb / ProjectDiscovery httpx / ffuf, адаптеры, NSE-профили, группировка крупных
графов, защищённое хранилище секретов и расширенный конструктор цепочек — следующие
этапы. Наличие одноимённой команды httpx не доказывает, что установлен инструмент
ProjectDiscovery. Полные характеристики VM Kali и установка/удаление через sudo
должны быть проверены на целевой системе; cloud offscreen-тест их не заменяет.

## Подготовленная облачная среда

```sh
bash scripts/setup_cloud.sh
QT_QPA_PLATFORM=offscreen /workspace/ghostmap-tools/bin/ghostmap-python -m unittest discover -s tests -v
python3 scripts/check_package.py
QT_QPA_PLATFORM=offscreen /workspace/ghostmap-tools/bin/ghostmap-python scripts/measure.py
```

Скрипт подготовки использует подписанные индексы Debian и проверенные APT
артефакты, распаковывает зависимости в `/workspace/ghostmap-tools` и не меняет
системные файлы. QtTest нужен только разработчику, в deb Depends его нет.
При наличии графической сессии:
`/workspace/ghostmap-tools/bin/ghostmap-python -m ghostmap`.
Без display в облаке доступны offscreen-проверки, а графическое использование
предназначено для Kali desktop. Прогресс и порядок продолжения — в PROGRESS.md.
