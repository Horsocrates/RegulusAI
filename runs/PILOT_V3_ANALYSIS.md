# PILOT v3 ANALYSIS — Двухагентный диалоговый пайплайн

**Дата:** 2026-02-16
**Модель:** Claude Opus 4.6 (с extended thinking)
**Архитектура:** Team Lead + Worker, последовательный домен-диалог
**Вопросов в пилоте:** 3

---

## 1. СВОДКА РЕЗУЛЬТАТОВ

| Вопрос | Expected | Got | Match? | Confidence | Time (s) | Total Tokens | TL calls | W calls | Total calls |
|--------|----------|-----|--------|------------|----------|-------------|----------|---------|-------------|
| MSV-CHEM-006 (озон) | I, II, IV, VI | I, II, IV, VI | **CORRECT** | 89% | 617.1 | 130 642 | 5 | 4 | 9 |
| MSV-CHEM-007 (медь) | I, II, IV, VI | I, II, IV | **WRONG** | 85% | 987.4 | 199 269 | 6 | 5 | 11 |
| MSV-BIO-001 (митохондрии) | I, III, V | I, III, V | **CORRECT** | 85% | 762.4 | 143 860 | 5 | 4 | 9 |

**Итого:** 2/3 (67%) правильных ответов. Один ответ ошибочен из-за избыточной химической строгости.

### Разбивка по токенам (input/output)

| Вопрос | TL input | TL output | W input | W output | Total |
|--------|----------|-----------|---------|----------|-------|
| Q1 (озон) | 66 130 | 12 011 | 34 204 | 18 297 | 130 642 |
| Q2 (медь) | 94 768 | 21 022 | 57 393 | 26 086 | 199 269 |
| Q3 (митохондрии) | 69 852 | 15 176 | 38 225 | 20 607 | 143 860 |
| **Среднее** | **76 917** | **16 070** | **43 274** | **21 663** | **157 924** |

---

## 2. ТОЧНОСТЬ ОТВЕТОВ

### Q1: Озон (MSV-CHEM-006) — CORRECT

**Expected:** I, II, IV, VI
**Got:** I, II, IV, VI

Пайплайн идеально определил все 6 вердиктов:
- I (окислитель сильнее O2): TRUE (98%) -- E°(O3)=+2.07V > E°(O2)=+1.23V
- II (длина связи O-O промежуточная): TRUE (99%) -- 1.21 < 1.278 < 1.48 A
- III (парамагнитен): FALSE (97%) -- ловушка O2/O3, замкнутая оболочка, диамагнетик
- IV (образуется в стратосфере): TRUE (99%) -- цикл Чепмена подтверждён
- V (линейная молекула): FALSE (99%) -- изогнутая, 116.8 градусов
- VI (термодинамически нестабилен): TRUE (97%) -- составное утверждение, все 3 компонента верны

**Особенности:** Наиболее чистый прогон. D3 и D4 были объединены (bundled). Конвергенция на первой итерации (iteration: 0). Ловушки III и V уверенно распознаны. Составное утверждение VI (E6a+E6b+E6link) было корректно декомпозировано.

### Q2: Медь (MSV-CHEM-007) — WRONG

**Expected:** I, II, IV, VI
**Got:** I, II, IV (без VI)

Пайплайн ОТВЕРГ утверждение VI о патине, хотя ожидаемый ответ включает его.

**Детальный анализ ошибки по диалогу:**

Цепочка рассуждений по утверждению VI прошла через 4 фазы:

1. **Phase 0 (TL init):** Team Lead в your_components отметил VI как "NUANCE TRAP -- partially true, precision matters" и предсказал {I, II, IV, VI}. Но пометил "requires careful scrutiny".

2. **D1 (iterate):** Критический инцидент -- Team Lead не включил полный текст утверждений в инструкцию для Worker. Worker получил только контекстные подсказки и попытался реконструировать вопрос. Два утверждения (I и IV) остались нераспознанными, III и V были перепутаны местами. Worker ЧЕСТНО пометил "CRITICAL GAP FLAG" и confidence 0.75. Team Lead признал свою ошибку: "The coverage failure is MY fault" и вернул D1 на переделку с полным текстом.

3. **D2 (pass):** Worker провёл анализ патины на 4 уровнях глубины:
   - Level 1 (популярный): "зелёная штука на меди = карбонат меди"
   - Level 2 (учебник): "основной карбонат меди Cu2(OH)2CO3 (малахит)"
   - Level 3 (функциональный): CuCO3 и Cu2(OH)2CO3 -- РАЗНЫЕ вещества
   - Level 4 (характер): чистый CuCO3 термодинамически нестабилен, не образуется атмосферно

   Ключевой вывод D2: "CuCO3 =/= Cu2(OH)2CO3 -- chemically distinct substances."

4. **D4 (dual reading):** Worker признал двойное прочтение:
   - Strict: FALSE (0.82) -- CuCO3 не то же, что Cu2(OH)2CO3
   - Informal: TRUE -- многие учебники упрощают до "copper carbonate"

5. **D5 (final call):** Worker принял решение: "MY CALL: Statement VI is FALSE." Аргумент: вопрос использует формальную IUPAC номенклатуру "copper(II) carbonate", что указывает на требование точности. Ответ {I, II, IV}.

6. **D6 (TL reflect):** Team Lead зафиксировал confidence 0.78 (ниже порога 85%). Выполнил FULL reflect. Отметил: "The pull toward 'VI is TRUE' comes partly from 'what exam answer keys commonly say' -- this is statistical consensus, not independent reasoning." Скорректировал confidence до 0.85 и принял threshold_reached.

**Корневая причина ошибки:**

Пайплайн проявил **избыточную химическую строгость**. Технически, различие между CuCO3 и Cu2(OH)2CO3 корректно. Однако в контексте стандартного экзаменационного вопроса (MCQ), "copper(II) carbonate" как описание патины является общепринятым упрощением. Вопрос НЕ тестирует знание IUPAC номенклатуры на уровне различия "basic carbonate" vs "carbonate" -- он тестирует, знает ли студент, что патина содержит карбонат меди, а не оксид или сульфат.

**Ирония ситуации:** Team Lead в Phase 0 ПРАВИЛЬНО предсказал {I, II, IV, VI} и пометил VI как "nuance trap". Однако пайплайн D2→D4→D5 убедил Worker (и затем TL) в обратном. Это классический случай, когда **чрезмерный анализ приводит к overthinking**.

**Дополнительный фактор:** Инцидент с iterate на D1 (Team Lead не передал текст вопроса) добавил 1 лишний вызов Worker и ~50K дополнительных токенов, удлинив прогон до 987 секунд.

### Q3: Митохондрии (MSV-BIO-001) — CORRECT

**Expected:** I, III, V
**Got:** I, III, V

Пайплайн верно определил все 6 вердиктов:
- I (кольцевая ДНК): TRUE (95%) -- канонический учебный факт
- II (одна мембрана): FALSE (99%) -- двойная мембрана, без двусмысленности
- III (основной сайт окислительного фосфорилирования): TRUE (99%) -- IMM = единственное место
- IV (во всех эукариотических клетках): FALSE (97%) -- контрпримеры: RBC, Monocercomonoides
- V (самовоспроизводятся независимо от клеточного цикла): TRUE (82%) -- стандартное учебное прочтение
- VI (pH матрикса ниже IMS): FALSE (99%) -- градиент перевёрнут в утверждении

**Особенности:** Утверждение V было наиболее спорным (82% confidence). Worker корректно идентифицировал двусмысленность "self-replicate" (полная автономия vs временная независимость), но обоснованно принял стандартное учебное прочтение. Финальный confidence 85% после D6-коррекции TL (raw 73% был overcautious из-за мультипликативного расчёта).

---

## 3. АНАЛИЗ ПАЙПЛАЙНА

### 3.1 Прогрессия доменов

| Вопрос | D1 | D2 | D3 | D4 | D5 | D6(TL) | Итого доменов |
|--------|----|----|----|----|----|----|---------------|
| Q1 (озон) | PASS | PASS | bundled с D4 | PASS | threshold_reached (D5 output) | FULL reflect | D1→D2→D3/D4→D5/D6 |
| Q2 (медь) | ITERATE→PASS | PASS | bundled с D4 | PASS | threshold_reached (D5 output) | FULL reflect | D1→D1redo→D2→D3/D4→D5/D6 |
| Q3 (митохондрии) | PASS | PASS | bundled с D4 | PASS | threshold_reached (D5 output) | FULL reflect | D1→D2→D3/D4→D5/D6 |

**Ключевые наблюдения:**

1. **D3 всегда bundled с D4.** Во всех 3 прогонах Team Lead объединил D3 (Framework Selection) и D4 (Comparison), поскольку framework очевиден (per-statement independent verification). Это хорошая оптимизация -- D3 как отдельный домен не несёт ценности для задач типа verification.

2. **D5 не исполняется Worker отдельно от D4.** D5-output приходит от Worker, но маркируется в dialogue.jsonl как `domain: "D4"` (в passport.json также). Фактически D4 и D5 тоже bundled -- Worker в одном ответе даёт и вердикты (D4), и композицию множества (D5).

3. **D5 никогда не достигается как отдельный домен.** Threshold_reached всегда происходит на рефлексии после D4/D5 output. Фактическая последовательность: D1 → D2 → D3+D4+D5(bundled) → D6(reflect) → threshold_reached.

4. **D6 (Reflection) всегда выполняется TL, не Worker.** Это by design -- TL делает FULL reflect после pipeline endpoint.

### 3.2 Конвергенция

| Вопрос | Iteration | Confidence (final) | Threshold domain | Причина конвергенции |
|--------|-----------|-------------------|------------------|----------------------|
| Q1 (озон) | 0 | 89% | После D4/D5 | All verdicts >=97%, computed confidence 89% > 85% |
| Q2 (медь) | 1 (D1 redo) | 85% (D6-adjusted) | После D4/D5 | TL adjusted 0.78 → 0.85, accepted with caveat |
| Q3 (митохондрии) | 0 | 85% (D6-adjusted) | После D4/D5 | TL adjusted raw 73% → 85%, inherent ambiguity E5 |

**Порог конвергенции (85%)** достигается на этапе D6-reflect Team Lead во всех случаях. В Q2 и Q3 Team Lead повышает confidence от Worker's raw value (0.78 и 0.73 соответственно), обосновывая overcautiousness мультипликативного расчёта. Это корректный статистический приём, но требует дисциплины -- завышение confidence не должно маскировать реальные пробелы.

### 3.3 Поведение iterate (Q2, D1)

В Q2 (медь) Team Lead допустил ошибку инструктирования: Phase 0 содержал описание вопроса, но не полный текст утверждений I-VI. Worker получил только контекстные подсказки и честно пометил пробел (CRITICAL GAP FLAG, confidence 0.75). Team Lead на reflect фазе зафиксировал: "The coverage failure is MY fault" и вернул D1 на iterate.

**Причина:** Скорее всего, промпт-шаблон pilot_v3.py не вставляет полный текст вопроса в инструкцию для Worker D1, а передаёт только Phase 0 analysis TL. Worker получает attention directives, sub-questions и your_components, но не verbatim statements.

**Последствия:** +1 вызов Worker, +1 вызов TL (reflect), ~50K дополнительных токенов, ~90 дополнительных секунд. Это системная ошибка, которая должна быть исправлена в промпт-шаблоне.

### 3.4 Эффективность токенов

| Метрика | Q1 (озон) | Q2 (медь) | Q3 (митохондрии) | Среднее |
|---------|-----------|-----------|-------------------|---------|
| Total tokens | 130 642 | 199 269 | 143 860 | 157 924 |
| TL input | 66 130 | 94 768 | 69 852 | 76 917 |
| TL output | 12 011 | 21 022 | 15 176 | 16 070 |
| W input | 34 204 | 57 393 | 38 225 | 43 274 |
| W output | 18 297 | 26 086 | 20 607 | 21 663 |
| Input/Output ratio | 3.3x | 1.8x | 1.8x | 2.3x |
| TL доля от total | 60% | 58% | 59% | 59% |
| W доля от total | 40% | 42% | 41% | 41% |

**Наблюдения:**

- TL потребляет ~59% всех токенов. Это ожидаемо: TL получает полный conspectus на каждом шаге, плюс Worker output, плюс thinking tokens (extended thinking).
- Q2 самый дорогой (199K) из-за iterate на D1 и дополнительного анализа VI.
- Input/Output ratio 2.3x означает, что контекст (system prompt + conspectus + dialogue history) растёт быстрее, чем генерируемый output.

**Стоимость при ценах Opus 4.6 (оценка):**

Предполагая $15/1M input, $75/1M output (цены Claude Opus):

| Вопрос | Input cost | Output cost | Total cost |
|--------|-----------|-------------|------------|
| Q1 | $1.50 | $2.27 | $3.77 |
| Q2 | $2.28 | $3.53 | $5.81 |
| Q3 | $1.62 | $2.68 | $4.30 |
| **Среднее** | **$1.80** | **$2.83** | **$4.63** |

~$4.63 за вопрос при средней задаче MCQ. Для HLE с трудными вопросами приемлемо, для production -- дорого.

---

## 4. КЭШИРОВАНИЕ

### 4.1 Данные о кэшировании

В passport.json НЕ содержатся отдельные поля `cache_read_tokens` и `cache_creation_tokens`. Данные о кэшировании агрегированы в `input_tokens` / `output_tokens` без декомпозиции.

### 4.2 Архитектурный анализ кэширования

Пайплайн использует `cache_control: ephemeral` на системном промпте. При v3 двухагентной архитектуре ситуация с кэшированием следующая:

**Team Lead:**
- Системный промпт (skills D6-ASK, D6-REFLECT) -- один и тот же для всех 5 вызовов TL.
- Каждый следующий вызов TL содержит ПОЛНЫЙ dialogue history + conspectus + Worker output.
- **Ожидаемая эффективность кэширования:** ВЫСОКАЯ для системного промпта (~5-10K токенов кэшируются). СРЕДНЯЯ для dialogue history (пересечение между вызовами, но каждый вызов добавляет ~5-15K нового контента).

**Worker:**
- Системный промпт (domain skills D1-D5) -- один и тот же для всех 4-5 вызовов Worker.
- Каждый вызов Worker получает НОВЫЙ промпт от TL (domain instruction + prior outputs).
- **Ожидаемая эффективность кэширования:** ВЫСОКАЯ для системного промпта. НИЗКАЯ для user message (каждый промпт уникален).

### 4.3 Оценка экономии

При эфемерном кэшировании системного промпта (допустим, ~8K токенов для TL, ~12K для Worker):
- TL: 5 вызовов x 8K = 40K кэшированных чтений (из 76K input) = ~52% экономии на input
- Worker: 4 вызова x 12K = 48K кэшированных чтений (из 43K input) = ~100%+ (если system prompt доминирует)

**Реальная экономия, вероятно, 25-40% от input cost**, что даёт ~$0.45-0.72 экономии на вопрос. Без кэширования стоимость была бы ~$5.5-6.0 за вопрос.

**Рекомендация:** Добавить явное логирование `cache_read_tokens` и `cache_creation_tokens` в passport.json для точного измерения.

---

## 5. ПРОБЛЕМЫ И РЕКОМЕНДАЦИИ

### 5.1 Проблема strict match (форматирование ответа)

**Симптом:** Ответ содержит полный аналитический текст, а не краткий формат "I, II, IV, VI".

**Пример (Q1):**
```
"answer": "**Statements I, II, IV, and VI are correct.**\n\n- **I. ✅** O₃ is a stronger oxidizing agent..."
```

Strict match `answer == expected` не срабатывает, т.к. ответ содержит обоснование, markdown-форматирование и эмодзи.

**Рекомендация:** Добавить постобработку ответа:
1. Извлечь строку после `answer:` или `**answer:**`
2. Парсить римские цифры (I, II, III, IV, V, VI) из этой строки
3. Нормализовать формат: `"I, II, IV, VI"` для strict match
4. Сохранять полный ответ как `answer_full`, а нормализованный как `answer_extracted`

### 5.2 Избыточная строгость Q2 (VI о патине)

**Симптом:** Пайплайн отверг общепринятое упрощение "copper(II) carbonate" для патины.

**Корневая причина:**
- D2 слишком глубоко погрузился в различие CuCO3 vs Cu2(OH)2CO3 (Level 4 analysis)
- Worker принял формальное IUPAC прочтение вместо экзаменационного
- Отсутствует механизм калибровки "уровня строгости" под тип вопроса

**Интересная деталь:** TL в Phase 0 ПРАВИЛЬНО предсказал {I, II, IV, VI} и пометил VI как "nuance trap -- partially true". Но пайплайн переубедил TL -- это случай, когда начальная интуиция TL была верна, а аналитический процесс ошибся.

**Рекомендации:**
1. **Добавить calibration level в Phase 0:** TL должен явно указать ожидаемый уровень строгости: "university textbook", "competition exam", "graduate level". Это передаётся как метаданные в каждый домен.
2. **Весить your_components prediction:** Если TL в Phase 0 предсказал {I, II, IV, VI} с confidence > 85%, а pipeline выдаёт {I, II, IV}, это должно тригерить повторную проверку VI, а не автоматическое принятие pipeline решения.
3. **Anti-overthinking guard:** Если verdict переключается с your_components prediction, требовать ДВОЙНОЕ подтверждение (Worker + TL independent re-evaluation) вместо однократного.

### 5.3 Пропуск D5 как отдельного домена

**Наблюдение:** D5 (Inference) никогда не исполняется как отдельный доменный pass. Он bundled c D4 -- Worker отвечает на D4 вопросы и сразу композирует D5 ответ.

**Является ли это проблемой?**

Для задач типа verification (MCQ) -- **нет**. D5 для верификации тривиален: собрать TRUE-множество из D4 вердиктов. Отдельный домен не нужен.

Для задач типа inference/synthesis -- **да, может быть проблемой**. Если вопрос требует нетривиального вывода из D4-данных (не просто подмножество), отдельный D5 необходим.

**Рекомендация:** Оставить bundling D3+D4+D5 для verification tasks. Для inference/synthesis tasks -- использовать полную последовательность D1→D2→D3→D4→D5.

### 5.4 Утечка текста вопроса (D1 iterate bug)

**Симптом:** В Q2 Worker не получил текст утверждений и был вынужден реконструировать его из контекстных подсказок.

**Причина:** TL prompt-шаблон передаёт Phase 0 analysis, но Phase 0 содержит вопрос в `your_components` таблице, а не как verbatim text для Worker. Worker получает "Statement III -- claim about reactivity" вместо точного текста.

**Рекомендация:** Добавить в промпт-шаблон TL→Worker явное включение:
```
## FULL QUESTION TEXT:
[verbatim question here]
```
Это устранит D1 iterate и сэкономит ~50K токенов на вопрос.

### 5.5 Токенная эффективность: 130K-199K на вопрос

**Контекст:**
- Q1: 130K (baseline, чистый прогон)
- Q2: 199K (с iterate + глубокий VI анализ)
- Q3: 143K (baseline + ambiguous E5)

**Проблема:** 130K -- это уже много для MCQ medium complexity. Для hard вопросов и open-ended задач может достигать 300K+, что:
- Приближается к лимиту контекстного окна
- Стоит $4-6 за вопрос
- Занимает 10-16 минут

**Возможные оптимизации:**
1. **Сжатие conspectus:** Вместо полного conspectus на каждом шаге, передавать "delta since last domain" + key verdicts summary. Экономия ~20-30% input tokens.
2. **Сокращение thinking tokens:** Extended thinking генерирует 200-500 слов на каждом шаге, часто повторяя уже известную информацию. Ограничить thinking budget.
3. **Adaptive depth:** Если all verdicts > 95% после D2, skip D4 deep analysis для очевидных элементов (II в Q3 = "single membrane" -- не требует D4 analysis, это однозначно FALSE).
4. **Merge D3+D4+D5 by default** для verification tasks (уже делается).

### 5.6 Время: 600-987 секунд на вопрос

| Вопрос | Время (s) | Время (мин) | Calls | ~с/call |
|--------|-----------|-------------|-------|---------|
| Q1 | 617 | 10.3 | 9 | 69 |
| Q2 | 987 | 16.4 | 11 | 90 |
| Q3 | 762 | 12.7 | 9 | 85 |

**Среднее:** 789 секунд (13.1 минут), ~81 секунд на вызов.

**Для HLE:** Приемлемо. HLE-оценка не ограничена по времени, и 13 минут на трудный вопрос -- это разумно для Opus 4.6 с thinking.

**Для production:** Неприемлемо. 13 минут на MCQ -- слишком долго для интерактивного использования.

**Оптимизации:**
- Параллельный запуск D1-D6 для разных вопросов (уже упомянуто в протоколе)
- Переход на Sonnet для D1/D3 (простые структурные домены), Opus только для D2/D4/D5
- Сокращение bundled domains снижает количество roundtrips

---

## 6. ОЦЕНКА v3 PIPELINE

### 6.1 Что работает хорошо

1. **Phase 0 (d6-ask):** Team Lead отлично декомпозирует вопрос, определяет your_components, идентифицирует ловушки. Во всех 3 вопросах Phase 0 prediction совпал с правильным ответом (даже в Q2 -- TL изначально предсказал правильно, {I, II, IV, VI}).

2. **ERR Framework:** Структурная декомпозиция Elements/Roles/Rules работает надёжно. Все элементы корректно идентифицированы, зависимости ациклические, уровни не нарушены.

3. **Trap detection:** Пайплайн распознал все встроенные ловушки:
   - Q1: O2/O3 paramagnetism (III), CO2/O3 geometry (V)
   - Q2: Activity series reversal (III), Cu+HCl impossibility (V)
   - Q3: Double membrane (II), RBC counterexample (IV), pH gradient direction (VI)

4. **Self-correction (D1 iterate):** Team Lead корректно идентифицировал СВОЮ ошибку (не включил текст) и вернул на переделку. Worker честно пометил пробел. Система self-healing работает.

5. **Confidence calibration:** Вердикты не все 99%. Реальная неопределённость отражена: III-ozone 97%, VI-copper 82%, V-mitochondria 82%. Это профессиональная калибровка.

6. **Disconfirming evidence search:** Каждый вердикт в D4 сопровождается явным поиском контраргументов. Это ключевой анти-confirmation-bias механизм.

7. **Chain traceability:** Каждый вывод D5 трассируется обратно: D1(recognized) → D2(clarified) → D4(evaluated) → D5(concluded). Ни одного "прыжка" без обоснования.

### 6.2 Что НЕ работает

1. **Overthinking на nuance traps:** Q2 VI показывает, что глубокий анализ может привести к НЕПРАВИЛЬНОМУ ответу. Pipeline убедил себя в ложном вердикте через "too rigorous" reasoning. Необходим механизм калибровки строгости.

2. **TL instruction leakage:** Team Lead не включает полный текст вопроса в Worker instruction. Это системная ошибка промпт-шаблона, а не pipeline-архитектуры.

3. **Token efficiency:** 130K-199K на MCQ medium -- это дорого. Для batch из 100 вопросов это $460 и ~22 часа. Нужны оптимизации.

4. **your_components override:** Когда pipeline противоречит your_components prediction, нет механизма "двойной проверки". TL просто принимает pipeline verdict. Нужен explicit disagreement resolution protocol.

5. **D5 не существует как отдельный домен** в текущей реализации. Для verification tasks это нормально, но для inference/synthesis tasks может быть проблемой.

### 6.3 Метрики надёжности

| Метрика | Значение | Комментарий |
|---------|----------|-------------|
| Accuracy (strict) | 0/3 (0%) | Strict match fails из-за форматирования |
| Accuracy (semantic) | 2/3 (67%) | Правильные ответы, но Q2 ошибка |
| Avg confidence | 86.3% | Калибровка адекватна |
| Confidence-accuracy alignment | Хорошо | Ошибка Q2 имела lowest confidence (85%), correct Q1 highest (89%) |
| Avg time | 789s (13.1 min) | Приемлемо для HLE |
| Avg tokens | 157K | Дорого, но работоспособно |
| Self-correction rate | 1/3 (33%) | Q2 потребовал iterate на D1 |
| False confidence | 0/3 | Ни одна ошибка не имела confidence > 90% |

### 6.4 Общий вердикт

**v3 двухагентный диалоговый пайплайн РАБОТОСПОСОБЕН**, но имеет системные проблемы:

**Сильные стороны:**
- Глубокий, прослеживаемый reasoning chain
- Честная калибровка confidence
- Robust trap detection
- Self-healing при ошибках инструктирования

**Слабые стороны:**
- Overthinking на nuanced вопросах (ведёт к ложным отрицаниям)
- Высокая стоимость токенов (~$4.60/вопрос)
- Медленное исполнение (~13 мин/вопрос)
- Bug в промпт-шаблоне (текст вопроса не передаётся Worker)

**Рекомендации для v3.1:**

| # | Приоритет | Рекомендация | Ожидаемый эффект |
|---|-----------|--------------|------------------|
| 1 | **P0** | Исправить промпт-шаблон: включить FULL QUESTION TEXT в Worker instruction | Устранит D1 iterate, -50K tokens, -90s |
| 2 | **P0** | Добавить answer extraction/normalization | Strict match заработает |
| 3 | **P1** | Добавить calibration level (textbook/exam/graduate) в Phase 0 | Предотвратит overthinking на nuance traps |
| 4 | **P1** | Implement disagreement protocol: если pipeline != your_components, требовать explicit re-evaluation | Предотвратил бы ошибку Q2 |
| 5 | **P2** | Логировать cache_read_tokens и cache_creation_tokens отдельно | Позволит оптимизировать кэширование |
| 6 | **P2** | Adaptive depth: skip deep D4 analysis для элементов с confidence > 95% после D2 | -20-30% tokens |
| 7 | **P3** | Рассмотреть Sonnet для D1/D3 (structural domains), Opus для D2/D4/D5 | -30-40% cost, -20% time |

---

## ПРИЛОЖЕНИЕ А: Хронология вызовов

### Q1 (озон) — 9 вызовов, 617s
```
TL → init (Phase 0 + D1 instruction)     → ~71s
W  → D1 output                            → ~52s
TL → D1 reflect (PASS) + D2 instruction   → ~120s
W  → D2 output                            → ~59s
TL → D2 reflect (PASS) + D3+D4 instruction→ ~104s
W  → D3+D4+D5 output                      → ~47s
TL → D3+D4 reflect (PASS) + D5 instruction→ ~56s
W  → D5 output (answer composition)       → ~47s
TL → FULL reflect (threshold_reached)     → ~61s
```

### Q2 (медь) — 11 вызовов, 987s
```
TL → init (Phase 0 + D1 instruction)      → ~93s
W  → D1 output (CRITICAL GAP)             → ~72s
TL → D1 reflect (ITERATE) + D1 redo instr → ~69s
W  → D1 correction pass                   → ~86s
TL → D1 redo reflect (PASS) + D2 instr    → ~122s
W  → D2 output (Level 4 on patina)        → ~72s
TL → D2 reflect (PASS) + D3+D4 instr      → ~116s
W  → D3+D4+D5 output                      → ~83s
TL → D4 reflect (PASS) + D5 instr         → ~86s
W  → D5 output (VI=FALSE call)            → ~105s
TL → FULL reflect (threshold_reached)     → ~83s
```

### Q3 (митохондрии) — 9 вызовов, 762s
```
TL → init (Phase 0 + D1 instruction)      → ~76s
W  → D1 output                            → ~56s
TL → D1 reflect (PASS) + D2 instruction   → ~115s
W  → D2 output                            → ~150s
TL → D2 reflect (PASS) + D3+D4 instr      → ~61s
W  → D3+D4+D5 output                      → ~99s
TL → D3+D4 reflect (PASS)                 → ~53s
W  → D5 output                            → ~39s
TL → FULL reflect (threshold_reached)     → ~113s
```

---

*Отчёт подготовлен автоматически на основе логов пилотного теста v3 pipeline.*
