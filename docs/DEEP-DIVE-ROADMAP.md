# AI-TrackEngineer — Deep Dive, Debilidades y Roadmap

> Documento de análisis técnico exhaustivo generado a partir de una revisión completa del código fuente (commit `01c1ce8`, 75 archivos Python en `src/`, 44 archivos de test). Objetivo: servir de mapa de trabajo para las próximas iteraciones, con foco en **frontend, motor de IA (Ollama) y análisis de datos de conducción**, sin depender de sesiones de conducción reales (uso de `--mock` y sesiones grabadas).

---

## 0. Resumen ejecutivo

AI-TrackEngineer es un proyecto con una **base de ingeniería sólida** (tipado estricto, Pydantic, arquitectura en capas, CI con lint+mypy+tests, 44 archivos de test) pero con un **desajuste severo entre "código escrito" y "código conectado"**. Hay módulos completos, testeados y exportados (`pattern_detector`, `gap_manager`, `CornerPredictor`/ML, todo `setup_lab`) que **nunca se ejecutan** en el flujo real (`main.py` → `dashboard/pump.py`). Es decir: una parte importante del "trabajo ya hecho" no está generando valor visible para el usuario todavía. Esto es una oportunidad barata: conectar cosas ya construidas es mucho más rápido que construirlas desde cero.

Las tres áreas que pediste (frontend, IA/Ollama, análisis) tienen problemas de naturaleza distinta:

| Área | Problema principal | Coste de arreglo |
|---|---|---|
| **Análisis de datos** | Solo se compara *tiempo* y *velocidad* contra la referencia. Los inputs reales (freno, gas, volante) se muestran pero nunca se analizan como eventos discretos. | Medio-alto, pero es puro procesamiento de señal sobre datos ya capturados — **no requiere ML ni conducir**. |
| **IA / Ollama** | Funciona, pero el contexto que recibe el LLM es pobre (hereda la pobreza del análisis) y no tiene memoria ni streaming. | Bajo una vez arreglado el análisis; el prompt ya es bueno. |
| **Frontend** | Un único HTML de 303 líneas, sin framework, sin componentes, sin tests, variables globales. | Alto (reescritura), pero paralelizable y de bajo riesgo (no toca el backend). |

Adicionalmente, hay una **cuarta área oculta** que conviene decidir explícitamente: **módulos dormidos** (ML, Setup Lab, Gap Manager, Pattern Detector) que están consumiendo espacio de mantenimiento sin dar valor. Hay que decidir, para cada uno, si se cablea, se recorta o se documenta como "experimental/desactivado".

---

## 1. Mapa de arquitectura real (qué está vivo, qué está muerto)

```
src/
├── telemetry/        [VIVO]   Captura SHM 60Hz + mock + conversión de frames
├── processing/        
│   ├── lap_segmenter  [VIVO]  Detecta fin de vuelta
│   ├── lap_trace       [VIVO]  Indexa una vuelta por posición normalizada
│   ├── corner_coach    [VIVO]  Feedback en vivo por curva (solo tiempo/velocidad)
│   └── message_queue   [VIVO]  Cola de prioridad para mensajes del feed
├── analysis/
│   ├── pipeline         [VIVO]  Orquesta todo el análisis por vuelta
│   ├── lap_comparator   [VIVO]  Delta de tiempo por curva (solo tiempo)
│   ├── tyre_model       [VIVO]  Estado térmico de neumáticos
│   ├── engine_monitor   [VIVO]  Alertas de rpm/motor
│   ├── session_report   [VIVO, pero solo por CLI] Resumen post-sesión
│   └── pattern_detector [MUERTO] Tendencias multi-vuelta — código completo, 0 llamadas
├── ai/
│   ├── advisor          [VIVO]  Heurística + fallback LLM
│   ├── context_builder  [VIVO]  Contexto textual para el LLM (pobre en datos)
│   ├── ollama_client    [VIVO]  Cliente stateless, sin memoria ni streaming
│   └── models (prompt)  [VIVO]  Buen system prompt, pero el modelo no puede cumplirlo
├── strategy/
│   ├── fuel_strategy    [VIVO]
│   ├── tyre_strategy    [VIVO]
│   ├── pit_strategy     [VIVO]
│   ├── mode_manager     [VIVO]  (Practice/Qualify/Race)
│   ├── session_detector [VIVO]
│   └── gap_manager      [MUERTO] Gaps a rivales / overcut-undercut — completo, 0 llamadas
├── ml/
│   ├── corner_predictor [MUERTO en runtime] Solo se usa en scripts/tests offline
│   ├── corner_dataset, features, lap_quality, recorded_session [solo training offline]
├── setup_lab/
│   ├── digital_twin, what_if, consistency_scorer, setup_io [MUERTO en runtime]
│   README: "physics twin dormant" — confirmado
├── knowledge/
│   ├── track_parser [VIVO]
│   └── car_physics/* [solo alimenta setup_lab, por tanto también dormido]
├── storage/            [VIVO]  SQLite + grabación CSV + adaptador InfluxDB opcional
├── dashboard/
│   ├── pump.py          [VIVO]  El verdadero "orquestador" runtime (más que main.py)
│   ├── hub/state/api    [VIVO]  WebSocket pub/sub
│   └── static/index.html [VIVO] Todo el frontend, un solo archivo
└── voice/               [VACÍO] Solo __init__.py — a pesar de aparecer en el README
```

**Hallazgo clave**: `src/dashboard/pump.py` es el verdadero punto de integración runtime (no `main.py`, que solo hace bootstrap). Cualquier módulo nuevo de análisis debe cablearse ahí para llegar al dashboard.

---

## 2. Debilidades detalladas por área

### 2.1 Análisis de datos (prioridad #1)

**Estado actual** (`src/analysis/pipeline.py:127-164`, `src/processing/corner_coach.py`, `src/analysis/lap_comparator.py`):
- `LapComparison.corner_delta()` solo resta `segment_time()` entre la vuelta actual y la de referencia. Es **puro delta temporal**, agregado a nivel de curva completa.
- `CornerCoach._brake_check()` compara velocidad en un único punto (5% antes de la curva) contra la referencia — no identifica *dónde* empezó a frenar el jugador, solo si va más rápido o más lento en ese punto fijo.
- No existe ningún concepto de:
  - **Punto de frenada** (posición/distancia donde `brake` cruza un umbral, p. ej. 10%).
  - **Trail braking** (superposición de frenada y volante durante la entrada en curva).
  - **Punto y pendiente de aplicación de acelerador** (cuándo vuelve a pisar gas tras el ápex, y qué tan agresivo/progresivo es).
  - **Suavidad de volante** (número de micro-correcciones, oscilación = pérdida de agarre y de tiempo).
  - **Velocidad mínima de curva (ápex speed)** comparada punto a punto, no solo al final del segmento.
- ~~`pattern_detector.py` completo, testeado, pero jamás invocado~~ **[RESUELTO — ver Fase 0]**: cableado a `dashboard/pump.py`, emite un evento `pattern` por WebSocket una vez hay 3+ vueltas válidas, renderizado en el feed del dashboard.
- ~~`session_report.py` solo se usaba desde el CLI~~ **[RESUELTO — ver Fase 0]**: ahora se emite un evento `session_report` tras cada vuelta y se muestra bajo el historial de vueltas en el dashboard.

**Por qué importa**: esto es la base de todo lo demás. El LLM no puede dar feedback específico ("frenaste 8m tarde") si el análisis no calcula ese dato. Arreglar esto desbloquea automáticamente mejoras en IA y en frontend (hay más que mostrar).

### 2.2 Motor IA / Ollama (prioridad #2)

**Estado actual** (`src/ai/ollama_client.py`, `src/ai/context_builder.py`, `src/ai/models.py`):
- `OllamaClient.complete()` (línea 29-37) hace **una llamada `chat()` sin historial**: cada vuelta es una conversación nueva. El modelo no puede notar progreso ("ya llevas 3 vueltas mejorando en T4") ni evitar repetirse.
- No hay streaming: el mensaje aparece entero de golpe en el feed (`onAdvice` en el HTML), lo cual además hace la UI menos "viva".
- `context_builder.build_lap_context()` (línea 18-57) solo pasa: nombre de pista, tiempo total, sectores, hasta 3 `corner_losses` (delta_s) y estado de neumáticos/motor. **No pasa ningún dato de inputs** (freno/gas/volante), así que el `SYSTEM_PROMPT` (que exige "referencia el punto concreto, velocidad exacta") no puede cumplirse con los datos disponibles — el modelo probablemente rellena con generalidades o alucina puntos.
- `advisor.py` tiene un buen patrón de fallback (heurística determinista si el LLM falla), eso está bien diseñado y no hace falta tocarlo.
- No hay **caché de contexto de pista** (physics/knowledge del coche vive en `src/knowledge/car_physics/*` pero solo se usa para el Setup Lab dormido — podría enriquecer el prompt de IA con límites reales del coche).
- No hay perfil de piloto persistente: nada que distinga "eres nuevo en esta pista" de "llevas 200 vueltas aquí y esto es una regresión".

### 2.3 Frontend (prioridad #3, pero paralelizable)

**Estado actual** (`src/dashboard/static/index.html`, 303 líneas):
- Un solo archivo: CSS inline (~100 líneas), HTML, y ~100 líneas de JS vanilla con estado en variables globales (`laps`, `trail`, `vmax`, `bestEverMs`...).
- Cero componentización: cada panel (timing, lap history, corner analysis, feed, tyres, trace) es manipulación directa de DOM vía `getElementById`.
- El canvas de "Telemetry Trace" (líneas 238-245) dibuja a mano speed/throttle/brake/steer con `moveTo/lineTo` — sin librería de charting, sin zoom, sin overlay de vuelta de referencia superpuesta (el usuario no puede ver "mi vuelta vs la mejor" en el gráfico de inputs, solo el número de delta).
- Sin tests de frontend (0 cobertura aquí, a diferencia del backend que tiene 44 archivos de test).
- Sin build step: no hay Vite/webpack, no hay TypeScript, no hay linting de JS.
- El propio README ya admite la deuda: *"Frontend: Embedded HTML + Canvas dashboard (React + Vite planned)"*.
- Responsive básico existe (`@media(max-width:900px)`, línea 107) pero es un único breakpoint.

### 2.4 Módulos dormidos (decisión pendiente, no urgente pero sí importante)

Estos módulos consumen mantenimiento (CI los testea, mypy los tipa) sin generar valor visible:

- **`strategy/gap_manager.py`** — Calcula gaps a rivales y tendencias de overcut/undercut. Exportado en `strategy/__init__.py` pero nunca llamado desde `pump.py`. Probablemente porque `ACPhysics`/`ACGraphics` de AC no siempre traen datos fiables de otros coches en todas las variantes de sesión — pero si el dato existe, es una funcionalidad de "carrera" muy vendible.
- **`ml/corner_predictor.py`** (+ `corner_dataset.py`, `features.py`, `lap_quality.py`, `recorded_session.py`) — Modelo XGBoost de 4 features (entry_speed, brake_point, gear, corner_index) entrenado offline vía `scripts/train_models.py`. Nunca se carga ni se usa en el pipeline en vivo. El README dice "Corner-time predictor pipeline + training on real data" (Done) pero omite que no está conectado a la experiencia de usuario.
- **`setup_lab/*`** (digital_twin, what_if, consistency_scorer, setup_io) — Simulador de física de punto-masa para responder "¿qué pasa si cambio la presión de neumáticos?". Documentado como "dormant" en el propio README. Depende de parsear archivos `.acd` empaquetados de AC (`src/knowledge/car_physics/*`), lo cual está señalado como pendiente.
- **`voice/`** — Directorio vacío en el momento de este análisis. **[EN DISEÑO — ver §2.6 y Fase 2.5]**: se ha decidido subir su prioridad porque aporta valor diferencial real (manos ocupadas con volante/pedales, no se puede leer una pantalla mientras se conduce). Ver diseño concreto abajo.

### 2.6 Módulo de voz — investigación y diseño (añadido tras revisión de WhimprFlow)

Se investigó [WhimprFlow](https://github.com/Blueturboguy07/WhimprFlow) (POC de dictado por voz, Rust/Tauri) como referencia de arquitectura, no de código a reutilizar directamente (stack distinto: Rust + whisper.cpp vs. nuestro Python + Ollama). Lo aprovechable:

- **Máquina de estados pura como reductor** (`whimpr-core/src/state/machine.rs`): `step(input) -> Vec<Action>` sin reloj ni hardware acoplado — el tiempo llega como `Tick`, las pulsaciones como `TriggerToken`. Resultado: toda la lógica de "mantener pulsado para hablar", doble-tap para modo manos-libres, cooldown anti-rebote y límite de duración de sesión es **determinista y 100% testeable sin micrófono ni hilos reales**. Este patrón es directamente portable a Python y es exactamente lo que necesitamos para no depender de hardware en los tests.
- **ASR local de una sola pasada por utterance**: `whisper-rs` con `single_segment=true`, `no_context=true`, `language` fijo — pensado para clips cortos tipo push-to-talk (no transcripción continua de larga duración), evitando la repetición de texto que produce whisper.cpp en modo multi-segmento. El equivalente en `faster-whisper` (ya declarado en `pyproject.toml` como dependencia opcional `voice`) es `condition_on_previous_text=False` + `vad_filter=True`.
- **Limpieza de transcripción vía LLM separado del motor de razonamiento**: WhimprFlow usa un LLM local (Qwen3-4B vía llama.cpp) solo para limpiar el texto (muletillas, autocorrección hablada, puntuación), no para responder. Nuestro caso es más simple: no necesitamos "limpiar" dictado libre, solo **transcribir una pregunta corta del piloto** ("¿cómo van los neumáticos?") y pasarla como texto al `RaceEngineerAdvisor`/Ollama ya existente — no hace falta un segundo modelo de limpieza.

**Diseño propuesto para AI-TrackEngineer** (adaptado al contexto de sim-racing, no de dictado de texto general):

1. **Interacción**: push-to-talk con una tecla/botón (idealmente un botón del volante si el usuario tiene uno mapeable, si no, una tecla libre del teclado). Mantener pulsado = grabar pregunta; soltar = transcribir + enviar al advisor + hablar la respuesta (TTS). Nada de always-on / wake-word en la v1: es más simple, más privado, y no compite con el audio del juego.
2. **Reutilizar el patrón `LLMClient`/`OllamaClient` ya existente** (`src/ai/llm.py`) para el ASR: definir un `AsrEngine` Protocol análogo (`transcribe(pcm: bytes) -> str`) con una implementación `FasterWhisperEngine`, manteniendo el mismo estilo arquitectónico del resto del proyecto (import perezoso de la librería pesada, como ya hace `OllamaClient`).
3. **La pregunta transcrita se inyecta como contexto adicional en `build_lap_context`** (o una función nueva `build_question_context`) para que el LLM responda a lo que el piloto preguntó en vez de solo dar el consejo genérico de la vuelta — esto conecta directamente con la Fase 2 (enriquecer IA).
4. **Reconocimiento de voz del piloto (hablante) mencionado por el usuario**: en v1 no hace falta diarización/identificación de hablante compleja — con un solo piloto por sesión, "reconocer tu voz" se resuelve simplemente con push-to-talk (solo se graba cuando el botón está pulsado, así que no hay ambigüedad de a quién pertenece el audio). Si en el futuro se quiere descartar ruido de fondo/radio de otros ocupantes, un modelo de verificación de hablante (speaker embedding, p. ej. con `speechbrain` o `resemblyzer`) sería una Fase posterior, no v1.
5. **TTS de la respuesta**: usar `edge-tts` (ya en las dependencias opcionales, gratis, buena calidad) como opción por defecto online-friendly, con `piper-tts` como alternativa 100% offline. Empezar solo con la respuesta de texto ya generada (no requiere cambios en el LLM), así el TTS es una capa puramente de salida.
6. **Testing sin hardware real**: como en WhimprFlow, la máquina de estados (punto 1) se testea con `Tick`/eventos sintéticos, sin micrófono. El `AsrEngine` se testea con un fake (igual que `LLMClient` ya se testea con `_FakeLLM` en `test_advisor.py`) alimentándole bytes de audio pregrabados de fixtures cortas, no con captura en vivo.

**Recomendación de producto**: no es necesariamente malo tener trabajo dormido, pero hay que ser explícito. O se cablea en las próximas fases, o se marca claramente como "experimental / fase futura" en el README para no generar expectativas ni deuda de mantenimiento fantasma.

### 2.5 Testing y CI

- 44 archivos de test, con CI en GitHub Actions ejecutando `ruff check`, `mypy`, y pytest con gate de cobertura (`ci.yml`). Esto es una fortaleza real, no una debilidad — pero:
  - No hay tests de frontend (0 en `static/index.html`).
  - No hay tests de integración end-to-end que unan telemetría mock → pipeline → WebSocket → payload JSON esperado por el HTML (el contrato entre backend y frontend no está verificado automáticamente; un cambio de nombre de campo en Python podría romper el HTML sin que CI lo detecte).
  - `ollama_client.py` está marcado `pragma: no cover` (adaptador de red, correcto no testearlo con red real, pero tampoco hay un test con servidor Ollama mockeado a nivel de contrato HTTP).

---

## 3. Roadmap de trabajo

Diseñado para poder ejecutarse **sin conducir**, usando `--mock` (`src/telemetry/mock.py`) y sesiones grabadas (`SessionRecorder` en `storage/session_recorder.py`, ya usado en `test_recorded_session.py`). Cada fase indica archivos afectados, y por qué ese orden.

### Fase 0 — Victorias rápidas (1-3 días, sin riesgo) — ✅ COMPLETADA

Objetivo: sacar valor de código que ya existe, sin escribir lógica nueva.

1. ✅ **Cablear `pattern_detector.detect_patterns`** en `dashboard/pump.py`: se acumulan `corner_losses` y tiempos de vuelta válidos por sesión y se emite un evento `pattern` por WebSocket una vez hay 3+ vueltas válidas (`_PATTERN_MIN_OCCURRENCES`). Renderizado en el feed del HTML (`onPattern`).
2. ✅ **Exponer `session_report.build_session_report` en vivo**: se emite un evento `session_report` tras cada vuelta completada (válida o no), mostrado bajo el historial de vueltas en el dashboard (`onSessionReport`).
3. ✅ **README actualizado** para reflejar que la Fase 5 (patrones + informes de sesión) ya está completa en vivo, no solo por CLI, y se enlaza este documento desde el README.
4. Tests añadidos: `test_run_session_publishes_session_report_every_lap`, `test_run_session_publishes_pattern_after_enough_valid_laps` en `tests/unit/test_dashboard_pump.py`. Cobertura de la suite completa: 97%.

### Fase 1 — Análisis de inputs de conducción (el core, 1-2 semanas) — ✅ COMPLETADA

Esto es lo más valioso y lo que desbloquea IA y frontend después.

1. ✅ **`LapTrace` extendida** (`processing/lap_trace.py`) con `brake_at`/`throttle_at`/`steer_at` (interpolación por posición, igual que `speed_at`), más `first_crossing`, `trail_braking_overlap` y `steering_reversals` como primitivas reutilizables (wrap-aware, para curvas que cruzan la línea de meta). Retrocompatible: los samples de 3 valores (posición, tiempo, velocidad) siguen funcionando, con freno/gas/volante a 0.0 por defecto.
2. ✅ **Nuevo módulo `analysis/input_analyzer.py`** con `corner_input_profile()` (punto de frenada, punto de reapertura de gas, solape de trail-braking, correcciones de volante para una vuelta) y `compare_corner_inputs()` (delta de cada métrica entre la vuelta actual y la de referencia, con conversión a metros vía `brake_point_delta_m`/`throttle_point_delta_m`). Nota: no se implementó `apex_speed_delta` explícito porque `speed_at()` ya permite ese cálculo directamente donde haga falta — no se justificaba una función adicional todavía.
3. ✅ **`CornerCoach` actualizado**: mantiene un buffer reciente de `(posición, tiempo, velocidad, freno, gas, volante)` y, al salir de una curva, reconstruye una traza parcial y la compara contra la referencia. El mensaje de coaching ahora es, por ejemplo, `"[T4] lost 0.18s vs best — braked 12m later, +1 steering correction"` en vez de solo `"[T4] lost 0.18s vs best"`. Degrada con elegancia (sin el detalle) cuando no hay suficientes datos de freno/gas para esa curva.
4. ✅ **Tests con datos sintéticos**: `test_lap_trace.py` (crossing, wraparound, trail braking, reversals), `test_input_analyzer.py` (perfil de curva, comparación, conversión a metros), `test_corner_coach.py` (mensaje enriquecido y fallback sin señal de input) — todo sin conducir, con traces construidas a mano. Suite completa: 308 tests, 97% cobertura.

### Fase 2 — Enriquecer el motor de IA (3-5 días, depende de Fase 1) — siguiente en la cola

1. **Reescribir `context_builder.build_lap_context`** para incluir, por cada corner_loss, el desglose de Fase 1 (punto de frenada, delta de ápex, perfil de gas). El prompt ya pide esto — solo falta dárselo.
2. **Memoria corta de sesión**: mantener las últimas N recomendaciones dadas (por curva) en `RaceEngineerAdvisor` para: (a) no repetir el mismo consejo vuelta tras vuelta si no ha habido cambio, (b) felicitar cuando el driver corrige algo señalado antes ("Mejoraste 0.15s en T4 tras el consejo anterior").
3. **Streaming de respuesta**: usar `chat(..., stream=True)` de la librería `ollama` y emitir tokens incrementales por WebSocket (nuevo tipo de evento `coaching_stream` o reutilizar `coaching`). Mejora sensación de "vivo" en el feed.
4. **Perfil de coche/pista opcional**: usar `knowledge/car_physics` (ya parseado, hoy solo alimenta el Setup Lab dormido) para inyectar límites reales (rpm óptimo, ángulo máximo de dirección) en el contexto del LLM, en vez de solo datos de telemetría cruda.

### Fase 2.5 — Módulo de voz (subida de prioridad tras investigación de WhimprFlow; ver §2.6)

Reordenada por delante del frontend porque: (a) depende de la Fase 2 (necesita al advisor respondiendo bien a texto antes de hablarlo), (b) es paralelizable a la Fase 3 (no toca el HTML), y (c) el propio usuario la señala como de alto valor diferencial — manos ocupadas en volante/pedales es el caso de uso donde una pantalla no sirve pero una voz sí.

1. **`src/voice/state_machine.py`**: puerto en Python del reductor puro de WhimprFlow (`step(input) -> list[Action]`), adaptado a push-to-talk simple (sin doble-tap/modo manos-libres por ahora, eso puede añadirse después si hace falta). Estados: `Idle`, `Recording`, `Finalizing`. Enteramente testeable sin hardware, sin asyncio, sin mocks de audio.
2. **`src/voice/asr.py`**: `Protocol AsrEngine` (`transcribe(pcm16k: bytes) -> str`), análogo a `src/ai/llm.py::LLMClient`. Implementación `FasterWhisperEngine` con import perezoso de `faster_whisper` (mismo patrón que `OllamaClient`), `condition_on_previous_text=False`, `vad_filter=True` (evita el problema de repetición de texto que documenta WhimprFlow en clips cortos).
3. **Integración con el advisor existente**: la pregunta transcrita se pasa a `RaceEngineerAdvisor`/`context_builder` como contexto adicional — no se crea un segundo pipeline de IA, se reutiliza el mismo Ollama ya integrado.
4. **`src/voice/tts.py`**: adaptador de salida (`edge-tts` por defecto, `piper-tts` como alternativa offline) que lee la respuesta de texto ya generada — capa puramente de salida, no requiere cambios en el LLM.
5. **Sin diarización en v1**: "reconocer tu voz" se resuelve con push-to-talk (solo se graba con el botón pulsado, sin ambigüedad de hablante). Verificación de hablante (speaker embedding) queda como posible Fase futura si se necesita ignorar ruido de fondo/radio.
6. **Tests**: máquina de estados con inputs sintéticos (como los tests de Rust de WhimprFlow, adaptados); `AsrEngine` testeado con un fake (mismo patrón que `_FakeLLM` en `test_advisor.py`) alimentado con fixtures de audio cortas pregrabadas, sin captura de micrófono en vivo.
7. **Dependencia ya declarada**: `pyproject.toml` ya tiene el extra `voice` (`faster-whisper`, `piper-tts`, `edge-tts`, `silero-vad`, `sounddevice`) sin usar — esta fase por fin le da uso.

### Fase 3 — Frontend (2-4 semanas, paralelizable con Fase 1/2/2.5 porque solo consume el mismo contrato WebSocket)

1. **Congelar el contrato WebSocket actual** (tipos `session`, `telemetry`, `lap`, `advice`, `strategy`, `coaching`, `mode`, `pattern`, `session_report`) como el punto de integración estable. Documentarlo en `docs/` con un ejemplo de payload por tipo — esto permite reescribir el frontend sin tocar Python en paralelo.
2. Migrar a **React + Vite + TypeScript** (como ya lo indica el propio README como plan), panel por panel, empezando por los de menor riesgo/mayor beneficio:
   - Lap History table → componente con sorting/filtrado.
   - Corner Analysis + Feed → listas virtualizadas, con distinción visual por prioridad (ya existe `Priority` en el backend, pero el HTML no lo usa aún para colorear tarjetas).
   - Telemetry Trace → sustituir el canvas manual por una librería ligera (uPlot o Visx) que permita overlay de vuelta actual vs referencia y zoom.
3. Añadir **tests de componente** (Vitest + Testing Library) y, si procede, un test E2E ligero con Playwright que arranque el server en `--mock` y verifique que el dashboard pinta datos.
4. Mantener un modo "single-file" de emergencia (o generar el build estático servido desde `dashboard/static/`) para no romper el flujo `uv run python -m src.main run`.

### Fase 4 — Decidir el destino de los módulos dormidos (1 semana de diseño + implementación variable)

Para cada uno, tomar una decisión explícita en vez de dejarlo indefinido:

- **Gap Manager**: si AC expone datos fiables de rivales en la sesión activa, cablear en `pump.py` y mostrar un panel "Gaps" en el dashboard (alto valor en modo Race). Si no, documentar la limitación y archivar el módulo con un comentario claro.
- **ML Corner Predictor**: decidir si vale la pena cargar el modelo entrenado en runtime para mostrar "tiempo esperado en esta curva" en vivo, comparándolo con el resultado heurístico ya existente. Si el dataset de entrenamiento es pequeño (pocas vueltas reales), quizás no aporte sobre la heurística determinista de Fase 1 — hay que medirlo, no asumirlo.
- **Setup Lab**: es el más grande y el más "dormido". Requiere parseo de `.acd` empaquetados (pendiente según el propio README). Si el interés real es el análisis de conducción (que es lo que has priorizado), esto puede quedar en pausa consciente una temporada — pero merece una línea clara en el README en vez de aparentar estar "en progreso" indefinidamente.
- **Voice**: ~~decisión pendiente~~ **[DECIDIDO]**: se sube de prioridad a Fase 2.5 (ver §2.6) por su alto valor diferencial. Se retira además la palabra "bidirectional" del subtítulo del README hasta que exista turno de conversación real, para no prometer de más mientras se construye.

### Fase 5 — Producto y mercado (continuo, en paralelo a todo lo anterior)

1. Grabar un **demo en vídeo corto** (con `--mock` o una sesión grabada) mostrando el feedback de frenada/gas/volante en acción — es el argumento de venta más fuerte y hoy no existe nada que lo muestre (no hay GIF/vídeo en el README).
2. Documentar en el README, con honestidad, **qué hace diferente a este proyecto** de MoTeC/RaceStudio (gratis, local, con IA) frente a apps de streaming de telemetría (con coaching accionable, no solo visualización).
3. Considerar publicar el corner-input-analyzer de la Fase 1 como una pieza reutilizable/aislada (librería o artículo técnico) — es el componente más original y con más "identidad técnica propia" del proyecto, buen material de portafolio independiente del resto de la app.

---

## 4. Cómo trabajar todo esto sin conducir

- `uv run python -m src.main run --mock` levanta el dashboard con telemetría simulada (`telemetry/mock.py`) — sirve para iterar frontend y wiring de eventos.
- `SessionRecorder`/sesiones grabadas (`storage/session_recorder.py`, ejercitado en `tests/unit/test_recorded_session.py`) permiten reproducir vueltas reales ya grabadas para validar los nuevos analizadores de input (Fase 1) contra datos reales sin necesidad de correr AC.
- Para la Fase 1, generar **fixtures sintéticas controladas** (p. ej. una vuelta "ideal" y una vuelta con frenada 10m tarde a propósito, construidas a mano en los tests) es más fiable que depender de vueltas reales para validar la lógica exacta de detección de puntos de frenada — los tests unitarios existentes (`test_lap_trace.py`, `test_lap_comparator.py`) ya siguen este patrón y se puede extender igual.
- El pipeline de CI (`ruff` + `mypy` + `pytest` con gate de cobertura) da una red de seguridad real para iterar rápido sin miedo a regresiones silenciosas.

---

## 5. Priorización sugerida (orden de ejecución)

1. ✅ Fase 0 (quick wins) — completada.
2. ✅ Fase 1 (análisis de inputs) — completada.
3. Fase 2 (IA) — depende directamente de Fase 1, es relativamente rápida una vez el dato existe. **Siguiente paso de trabajo.**
4. Fase 2.5 (voz) — depende de que el advisor responda bien a texto (Fase 2); no bloquea ni bloquea al frontend, puede solaparse con la Fase 3.
5. Fase 3 (frontend) — puede arrancar en paralelo a Fase 1/2/2.5 en cuanto el contrato WebSocket esté congelado (punto 1 de Fase 3), usando datos mock mientras las demás avanzan.
6. Fase 4 (módulos dormidos) — decisión de producto, no bloquea nada, puede ir intercalada.
7. Fase 5 (mercado) — continuo, pero el vídeo demo cobra sentido real después de Fase 1, y ahora también tras la Fase 2.5 (una demo con voz es un argumento de venta más fuerte que solo texto).

---

## 6. Riesgos y trade-offs a tener en cuenta

- **Sobre-ingeniería en Fase 1**: es tentador construir un modelo de "estilo de conducción" muy elaborado. Empezar con umbrales simples y deterministas (como ya hace el resto del proyecto: `tyre_model.py`, `engine_monitor.py`) es coherente con el estilo actual del código y más fácil de explicar en el prompt del LLM.
- **Frontend a medio migrar**: si se empieza React sin congelar el contrato WebSocket, se corre el riesgo de tener que rehacer partes cuando cambien los payloads de Fase 1/2. Por eso el punto 1 de Fase 3 es congelar el contrato primero.
- **Módulos dormidos como deuda invisible**: cada módulo dormido que se mantiene "por si acaso" cuesta mypy/CI/tiempo de lectura sin dar valor. Mejor decidir activamente (Fase 4) que dejarlo indefinido.
- **Voice en el README**: ~~riesgo~~ **[MITIGADO]** — el subtítulo ya no promete "bidirectional" hasta que exista de verdad; se actualizará de nuevo cuando la Fase 2.5 entregue una v1 funcional.
- **Voz — dependencias pesadas de audio/modelo**: `faster-whisper` + un modelo Whisper descargado son un coste de setup no trivial para quien clone el repo. Mantenerlo como *extra* opcional (`uv sync --extra voice`), como ya está declarado, para no penalizar a quien solo quiere telemetría + IA de texto.
- **Voz — latencia percibida**: transcribir + consultar a Ollama + sintetizar voz puede tardar 1-3s en hardware modesto; hay que medirlo temprano (Fase 2.5, punto 6) para decidir si hace falta feedback visual ("escuchando… pensando…") mientras se genera la respuesta, en vez de asumir que será instantáneo.
