# Regulus AI — Инструкция для Claude Code

## Контекст

У нас УЖЕ ЕСТЬ готовое ядро **LogicGuard MVP**. Не нужно писать с нуля!

### Существующие файлы (скопируй в проект):
```
logicguard/
├── types.py           # ✅ Все типы данных (Node, Status, IntegrityGate...)
├── zero_gate.py       # ✅ Zero-Gate механизм  
├── status_machine.py  # ✅ L5-Resolution
├── sensor.py          # 🔶 HeuristicExtractor + заглушка LLM
├── engine.py          # ✅ LogicGuardEngine
├── visualization.py   # ✅ ASCII + Graphviz
├── paradox_demo.py    # ✅ Демо парадоксов
└── test_engine.py     # ✅ Тесты
```

---

## Шаг 1: Подготовка

```powershell
# Создай папку проекта
mkdir C:\Users\aleks\Projects\Regulus-AI
cd C:\Users\aleks\Projects\Regulus-AI

# Скопируй туда ВСЕ файлы:
# - Документы: REGULUS_CLI_SPEC.md, CLAUDE.md
# - Ядро LogicGuard: types.py, zero_gate.py, status_machine.py, sensor.py, engine.py, visualization.py
# - Тесты: test_engine.py
# - Примеры: sample_reasoning.json, paradox_demo.py
```

---

## Шаг 2: Запуск Claude Code

```powershell
cd C:\Users\aleks\Projects\Regulus-AI
claude
```

---

## Шаг 3: Команда для Claude Code

Скопируй и вставь:

---

```
Прочитай REGULUS_CLI_SPEC.md и CLAUDE.md для контекста.

У нас уже есть готовое ядро LogicGuard. Твоя задача — адаптировать его в Regulus AI и добавить LLM-интеграцию.

**Фаза 1: Реструктуризация (сейчас)**

1. Инициализируй проект:
   ```bash
   uv init
   uv add anthropic openai rich typer pydantic httpx python-dotenv pytest pytest-asyncio
   ```

2. Создай структуру, перенеся существующий код:
   ```
   regulus/
   ├── __init__.py
   ├── __main__.py
   ├── cli.py                    # НОВЫЙ: Typer CLI
   │
   ├── core/
   │   ├── __init__.py
   │   ├── types.py              # ← из logicguard/types.py
   │   ├── zero_gate.py          # ← из logicguard/zero_gate.py
   │   ├── status_machine.py     # ← из logicguard/status_machine.py
   │   ├── weight.py             # Извлечь из существующего кода
   │   └── engine.py             # ← из logicguard/engine.py
   │
   ├── llm/
   │   ├── __init__.py
   │   ├── client.py             # НОВЫЙ: Базовый LLM клиент
   │   ├── claude.py             # НОВЫЙ: Claude API
   │   ├── openai.py             # НОВЫЙ: OpenAI API
   │   └── sensor.py             # ← адаптировать из logicguard/sensor.py
   │
   ├── ui/
   │   ├── __init__.py
   │   └── console.py            # ← из logicguard/visualization.py + Rich
   │
   └── prompts/
       ├── __init__.py
       └── correction.py         # НОВЫЙ: Fix prompts из спецификации
   
   tests/
   ├── test_core.py              # ← из test_engine.py
   └── test_llm.py               # НОВЫЙ
   ```

3. Обнови импорты во всех файлах (logicguard → regulus.core)

4. Проверь, что тесты проходят:
   ```bash
   uv run pytest tests/test_core.py -v
   ```

**Фаза 2: LLM интеграция (после подтверждения Фазы 1)**

1. Реализуй `regulus/llm/client.py`:
   ```python
   from abc import ABC, abstractmethod
   
   class LLMClient(ABC):
       @abstractmethod
       async def generate(self, prompt: str, system: str = None) -> str:
           ...
   ```

2. Реализуй `regulus/llm/claude.py`:
   ```python
   from anthropic import AsyncAnthropic
   
   class ClaudeClient(LLMClient):
       def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
           self.client = AsyncAnthropic(api_key=api_key)
           self.model = model
       
       async def generate(self, prompt: str, system: str = None) -> str:
           response = await self.client.messages.create(
               model=self.model,
               max_tokens=2048,
               system=system or "",
               messages=[{"role": "user", "content": prompt}]
           )
           return response.content[0].text
   ```

3. Реализуй настоящий LLM Sensor в `regulus/llm/sensor.py`:
   - Используй SYSTEM_PROMPT из существующего sensor.py
   - Парси JSON-ответ модели в GateSignals + RawScores

**НЕ ПРИСТУПАЙ к Фазе 2, пока не подтвердишь завершение Фазы 1!**

Покажи мне:
1. Созданную структуру папок
2. Результат `uv run pytest tests/test_core.py -v`
```

---

## Ожидаемый результат Фазы 1

```
regulus/
├── __init__.py
├── core/
│   ├── types.py         # 300+ строк
│   ├── zero_gate.py     # 200+ строк  
│   ├── status_machine.py # 250+ строк
│   └── engine.py        # 150+ строк
└── ...

tests/test_core.py: 22 tests passed ✅
```

---

## После завершения всех фаз

Regulus AI будет работать так:

```bash
# Простой запрос
regulus "Is P=NP solvable?"

# С выбором провайдера
regulus --provider claude "Explain quantum entanglement"

# Verbose режим (показать дерево рассуждений)
regulus -v "Is democracy the best system?"
```

---

*Theory of Systems — Regulus AI Project*
