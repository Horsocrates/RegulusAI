# HLE Test Launch Prompts

Вставь один из промптов ниже в новый чат Claude Code.

---

## Промпт: Запуск P1 + P2 (полный цикл без судейства)

```
Прочитай инструкции: tests/HLE/RUN_INSTRUCTIONS.md

Задача: запустить P1 (baseline) и P2 (Regulus v2) на всех батчах.

ПРАВИЛА КОНТАМИНАЦИИ (КРИТИЧНО):
- НИКОГДА не читай .judge_only/ и любые файлы внутри
- НИКОГДА не читай файлы с ответами
- Файлы вопросов questions/*.json — безопасны (без поля answer)
- Результаты пишутся напрямую в .judge_only/ скриптами

Рабочая директория: C:\Users\aleks\Desktop\regulusai

Шаги:
1. Запусти P1 на всех батчах параллельно (run_baseline.py)
2. Запусти P2 на всех батчах параллельно (run_regulus.py)
3. Дождись завершения всех процессов
4. Выведи сводку: сколько вопросов обработано, время, ошибки

НЕ запускай judge.py и compare.py — это делается в отдельной сессии.
```

---

## Промпт: Только P1 (baseline)

```
Прочитай: tests/HLE/RUN_INSTRUCTIONS.md

Запусти ТОЛЬКО P1 baseline (run_baseline.py) на всех батчах параллельно.
Рабочая директория: C:\Users\aleks\Desktop\regulusai

КОНТАМИНАЦИЯ: не читай .judge_only/, не читай ответы.
Дождись завершения, выведи сводку.
```

---

## Промпт: Только P2 (Regulus v2)

```
Прочитай: tests/HLE/RUN_INSTRUCTIONS.md

Запусти ТОЛЬКО P2 Regulus v2 (run_regulus.py) на всех батчах параллельно.
Рабочая директория: C:\Users\aleks\Desktop\regulusai

КОНТАМИНАЦИЯ: не читай .judge_only/, не читай ответы.
Дождись завершения, выведи сводку.
```

---

## Промпт: Судейство + сравнение (ОТДЕЛЬНАЯ сессия)

```
Прочитай: tests/HLE/RUN_INSTRUCTIONS.md

Задача: запустить судейство (judge.py) и сравнение (compare.py).
Рабочая директория: C:\Users\aleks\Desktop\regulusai

Эта сессия МОЖЕТ читать .judge_only/ — это единственная сессия где это разрешено.

Шаги:
1. Запусти judge.py для P1 на всех батчах (--participant p1)
2. Запусти judge.py для P2 на всех батчах (--participant p2)
3. Запусти compare.py --all
4. Покажи итоговую таблицу: accuracy P1 vs P2, LIFT/BOTH/HURT/NEITHER
```

---

## Промпт: Подготовка новых вопросов

```
Прочитай: tests/HLE/RUN_INSTRUCTIONS.md

Подготовь новые батчи вопросов из HLE датасета.
Рабочая директория: C:\Users\aleks\Desktop\regulusai

Параметры:
- seed: {SEED}
- батчей: {N}
- вопросов в батче: 10

Команда: .venv\Scripts\python.exe tests/HLE/prepare_questions.py --seed {SEED} --n-batches {N} --batch-size 10

Проверь что в сгенерированных questions/*.json нет поля "answer".
```

---

## Промпт: P3 Agent Pipeline (slash commands)

```
Прочитай: tests/HLE/RUN_INSTRUCTIONS.md (секция "P3: Agent-Based Pipeline")

Задача: обработать вопрос через полный D1-D6 пайплайн Theory of Systems.

КОНТАМИНАЦИЯ: не читай .judge_only/, не читай ответы.

Рабочая директория: C:\Users\aleks\Desktop\regulusai
Промпты доменов: .claude/commands/ (analyze.md, d1-recognize.md ... d6-reflect.md)

Вопрос: {ВСТАВЬ ВОПРОС}

Шаги:
1. Создай рабочую папку tests/HLE/workspace/q_{ID}/
2. Запусти /analyze с текстом вопроса
3. Team Lead проведёт вопрос через D1→D2→D3→D4→D5→D6
4. Финальный ответ будет в result.json
```
