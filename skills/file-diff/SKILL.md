# Skill: file-diff

Сравнение двух файлов с выводом различий в формате unified diff.

## Когда использовать

- Сравнить две версии файла
- Увидеть изменения между файлами
- Проверить разницу перед/после рефакторинга
- Сравнить конфигурационные файлы

## Как использовать

Просто попроси:
- "покажи разницу между file1.go и file2.go"
- "diff эти два файла"
- "сравни файл A и файл B"

## Что делает

1. Запрашивает пути к двум файлам для сравнения
2. Запускает `diff -u файл1 файл2`
3. Выводит unified diff с контекстом
4. Показывает статистику изменений

## Примеры

```
file-diff apps/sam-adapter/internal/controllers/api/pickup_points.go apps/sam-adapter/internal/controllers/api/pickup_points.go.bak
```

```
diff old.yaml new.yaml
```

## Реализация

Команда: `diff -u <file1> <file2>`

Выходной формат: unified diff с 3 строками контекста (стандарт)

Base directory for this skill: /home/ruslan/.config/opencode/skills/file-diff
