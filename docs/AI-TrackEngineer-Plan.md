# AI-TrackEngineer

## Descripcion del Proyecto

AI-TrackEngineer es un asistente de ingeniero de pista basado en inteligencia artificial para Assetto Corsa (original). El sistema captura telemetria en tiempo real a traves de la Shared Memory API, analiza el rendimiento de conduccion vuelta a vuelta y curva a curva, y proporciona recomendaciones inteligentes a traves de un dashboard web Y comunicacion de voz bidireccional. Incluye modelos predictivos de ML, estrategia de carrera, y un Setup Lab basado en fisica (digital twin).

## Rol del Asistente

Eres un ingeniero de pista experto y desarrollador senior implementando el proyecto AI-TrackEngineer. Debes:

- Escribir Python limpio y tipado (type hints en todas las funciones y clases)
- Seguir principios SOLID y arquitectura limpia (capas bien separadas, inyeccion de dependencias)
- Implementar tests unitarios y de integracion para cada modulo
- Usar async/await para todo lo que sea tiempo real (telemetria, WebSocket, voz)
- Documentar decisiones de arquitectura y trade-offs en el codigo
- Priorizar rendimiento en el loop de telemetria (60Hz no negociable)
- Manejar errores de forma robusta (el sistema no puede crashear en medio de una carrera)
- Escribir commits descriptivos y mantener el codigo modular y extensible

---

## Arquitectura

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              ASSETTO CORSA                                           │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐  ┌──────────────────────┐  │
│  │  SHM API     │  │ Track Files  │  │ Car Physics    │  │ AC Python App        │  │
│  │ (Physics,    │  │ (ai_line.bin,│  │ Files (.ini,   │  │ (Extended data       │  │
│  │  Graphics,   │  │  track.ini)  │  │  .lut)         │  │  bridge)             │  │
│  │  Static)     │  │              │  │                │  │                      │  │
│  └──────┬───────┘  └──────┬───────┘  └───────┬────────┘  └──────────┬───────────┘  │
└─────────┼──────────────────┼──────────────────┼──────────────────────┼──────────────┘
          │                  │                  │                      │
          ▼                  ▼                  ▼                      ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                         TELEMETRY CAPTURE LAYER                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐  ┌──────────────────────┐  │
│  │ SHM Reader   │  │ Track Parser │  │ Car Physics    │  │ Extended Data        │  │
│  │ (60Hz,       │  │ (corners,    │  │ Parser         │  │ Bridge               │  │
│  │  mmap/ctypes)│  │  sectors)    │  │ (aero, tyres,  │  │                      │  │
│  │              │  │              │  │  suspension)   │  │                      │  │
│  └──────┬───────┘  └──────┬───────┘  └───────┬────────┘  └──────────┬───────────┘  │
└─────────┼──────────────────┼──────────────────┼──────────────────────┼──────────────┘
          │                  │                  │                      │
          ▼                  ▼                  ▼                      ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                       DATA PROCESSING PIPELINE                                       │
│  ┌────────────┐ ┌──────────────┐ ┌──────────────┐ ┌───────┐ ┌────────┐ ┌────────┐ │
│  │    Lap     │ │   Corner     │ │Normalization │ │ Delta │ │ Sector │ │Anomaly │ │
│  │Segmentation│ │  Detection   │ │              │ │ Calc  │ │ Splits │ │Flagging│ │
│  └─────┬──────┘ └──────┬───────┘ └──────┬───────┘ └───┬───┘ └───┬────┘ └───┬────┘ │
└────────┼────────────────┼────────────────┼─────────────┼─────────┼───────────┼──────┘
         │                │                │             │         │           │
         ▼                ▼                ▼             ▼         ▼           ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                            STORAGE LAYER                                             │
│         ┌─────────────────────────────┐    ┌─────────────────────────────┐          │
│         │   InfluxDB 2.x (Docker)     │    │      SQLite                 │          │
│         │   - Telemetria time-series  │    │   - Sesiones, vueltas       │          │
│         │   - Metricas por vuelta     │    │   - Configs, setups         │          │
│         │   - Datos de sensores       │    │   - Perfil del piloto       │          │
│         └──────────────┬──────────────┘    └──────────────┬──────────────┘          │
└────────────────────────┼──────────────────────────────────┼─────────────────────────┘
                         │                                  │
          ┌──────────────┴──────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                          ANALYSIS ENGINE                                              │
│  ┌──────────────────┐ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐  │
│  │ Lap Comparator   │ │Pattern Detector │ │ Tyre & Engine   │ │ Handling Scorer │  │
│  │ (best vs current,│ │(frenadas,       │ │ Monitor         │ │ (sub/sobre-vir, │  │
│  │  sector deltas)  │ │ trazadas, apex) │ │ (desgaste, temp)│ │  consistencia)  │  │
│  └────────┬─────────┘ └────────┬────────┘ └────────┬────────┘ └────────┬────────┘  │
└───────────┼─────────────────────┼───────────────────┼───────────────────┼───────────┘
            │                     │                   │                   │
            ▼                     ▼                   ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                             ML ENGINE                                                 │
│  ┌──────────────────┐ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐  │
│  │ Corner Predictor │ │Tyre Degradation │ │ Optimal Lap     │ │ Setup→Behavior  │  │
│  │ (tiempo optimo   │ │ Model           │ │ Calculator      │ │ Model           │  │
│  │  por curva)      │ │ (vida restante) │ │ (vuelta ideal)  │ │ (efecto cambios)│  │
│  └────────┬─────────┘ └────────┬────────┘ └────────┬────────┘ └────────┬────────┘  │
└───────────┼─────────────────────┼───────────────────┼───────────────────┼───────────┘
            │                     │                   │                   │
            ▼                     ▼                   ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                      AI RECOMMENDATION ENGINE                                        │
│  ┌───────────────┐  ┌─────────────────────────────────────┐  ┌───────────────────┐  │
│  │Context Builder│  │ LLM Provider                        │  │ Output Modes      │  │
│  │(estado actual,│─▶│ Primary: GitHub Copilot API         │─▶│ - Real-time tips  │  │
│  │ historial,   │  │ Fallback: Ollama (Mistral/Llama 3)  │  │ - Post-session    │  │
│  │ perfil)      │  │                                     │  │   analysis        │  │
│  └───────────────┘  └─────────────────────────────────────┘  └────────┬──────────┘  │
└───────────────────────────────────────────────────────────────────────┼──────────────┘
                                                                        │
            ┌───────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           VOICE ENGINE                                                │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────┐ ┌────────────┐  │
│  │ Whisper STT  │ │  Piper TTS   │ │  Silero VAD  │ │  Intent    │ │   Voice    │  │
│  │ (faster-     │ │ / Edge TTS   │ │ (deteccion   │ │  Router    │ │  Manager   │  │
│  │  whisper)    │ │              │ │  actividad)  │ │            │ │ (push/vox) │  │
│  └──────────────┘ └──────────────┘ └──────────────┘ └────────────┘ └────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                         RACE STRATEGIST                                               │
│  ┌──────────────────┐ ┌──────────────────────────────────┐ ┌─────────────────────┐  │
│  │ Session Mode     │ │ Strategy Modules                 │ │ Session Modes       │  │
│  │ Detector         │ │ - Fuel Calculator                │ │ - Practice          │  │
│  │ (auto + voice    │ │ - Pit Window Optimizer           │ │ - Qualifying        │  │
│  │  override)       │ │ - Gap Manager                    │ │ - Race              │  │
│  │                  │ │ - Tyre Strategy                  │ │                     │  │
│  └──────────────────┘ └──────────────────────────────────┘ └─────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                            SETUP LAB                                                  │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────┐ ┌────────────┐  │
│  │   Physics    │ │ Digital Twin │ │   What-If    │ │  Driver    │ │Consistency-│  │
│  │   Parsers    │ │ (modelo del  │ │  Simulator   │ │  Profile   │ │   Aware    │  │
│  │ (.ini,.lut)  │ │  coche)      │ │              │ │            │ │Recommender │  │
│  └──────────────┘ └──────────────┘ └──────────────┘ └────────────┘ └────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                     WEB DASHBOARD (FastAPI + React)                                   │
│  ┌───────────┐ ┌───────────┐ ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐  │
│  │   Live    │ │    Lap    │ │   AI    │ │  Setup   │ │ Strategy │ │   Voice   │  │
│  │ Telemetry │ │Comparison │ │  Feed   │ │  Panel   │ │   View   │ │  Status   │  │
│  │ (WebSocket│ │ (graficos │ │(consejos│ │(digital  │ │(fuel,pit,│ │(STT/TTS,  │  │
│  │  30Hz)    │ │  overlay) │ │ en vivo)│ │ twin UI) │ │ gaps)    │ │  estado)  │  │
│  └───────────┘ └───────────┘ └─────────┘ └──────────┘ └──────────┘ └───────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Decisiones Tecnicas

| Aspecto | Decision | Justificacion |
|---------|----------|---------------|
| Juego | Assetto Corsa (original) | SHM API documentada, ecosistema modding activo, fisica realista |
| Lenguaje | Python 3.12+ | Ecosistema ML/AI, ctypes para SHM, FastAPI async |
| Telemetria | Shared Memory (mmap/ctypes) | 60Hz sin overhead de red, acceso directo a structs |
| IA primaria | GitHub Copilot API | Modelos potentes, buena relacion coste/calidad |
| IA fallback | Ollama (Mistral/Llama 3) | Sin dependencia de internet, privacidad |
| Frontend | React + Vite | Ecosistema maduro, graficos con recharts/d3 |
| Time-series DB | InfluxDB 2.x (Docker) | Optimizado para telemetria, queries temporales eficientes |
| Metadata DB | SQLite | Ligero, sin servidor, suficiente para metadata |
| Comunicacion RT | WebSocket (FastAPI) | Baja latencia, bidireccional |
| Voice STT | faster-whisper (local) | Baja latencia, funciona offline, modelos optimizados |
| Voice TTS | Piper TTS (local) / Edge TTS (cloud) | Natural, baja latencia, opcion offline + cloud |
| Voice VAD | Silero VAD | Ligero, preciso, sin GPU, ideal para deteccion continua |
| ML Models | scikit-learn + XGBoost | Ideal para datos tabulares de telemetria, rapido en inferencia |
| Setup Knowledge | Physics-based + empirico | Base solida en fisica real + personalizacion por piloto |
| Deteccion sesion | Auto-detect desde AC + override por voz | Flexibilidad, el piloto siempre tiene la ultima palabra |
| Package manager | uv | Rapido, moderno, lockfile deterministico |

---

## Estructura del Proyecto

Estructura completa del proyecto incluyendo las 9 fases de implementacion.

```
ai-track-engineer/
├── pyproject.toml
├── docker-compose.yml
├── config/
│   ├── settings.yaml
│   ├── tracks/                    # Track-specific configs
│   └── voice/
│       ├── intents.yaml           # Voice command definitions
│       └── responses.yaml         # Response templates
├── src/
│   ├── __init__.py
│   ├── main.py                    # Entry point, orchestration
│   ├── telemetry/
│   │   ├── __init__.py
│   │   ├── shm_reader.py         # Lectura shared memory AC
│   │   ├── shm_structs.py        # Structs ctypes de AC SHM
│   │   ├── models.py             # Pydantic models de telemetria
│   │   └── ac_bridge.py          # Bridge para datos extendidos
│   ├── processing/
│   │   ├── __init__.py
│   │   ├── lap_segmenter.py      # Detectar inicio/fin de vuelta
│   │   ├── corner_detector.py    # Segmentar curvas
│   │   ├── normalizer.py         # Normalizar por distancia/tiempo
│   │   └── delta.py              # Calculo de deltas entre vueltas
│   ├── knowledge/
│   │   ├── __init__.py
│   │   ├── track_parser.py       # Parser ai_line.bin, track.ini
│   │   ├── track_db.py           # Base de conocimiento circuitos
│   │   ├── car_physics/
│   │   │   ├── __init__.py
│   │   │   ├── power_parser.py   # Parser power.lut (curva potencia)
│   │   │   ├── tyre_parser.py    # Parser tyres.ini (modelo termico, grip)
│   │   │   ├── aero_parser.py    # Parser aero.ini (downforce, drag)
│   │   │   ├── suspension_parser.py  # Parser suspensions.ini
│   │   │   ├── drivetrain_parser.py  # Parser drivetrain.ini
│   │   │   ├── brake_parser.py   # Parser brakes.ini
│   │   │   └── car_model.py      # Modelo unificado del coche
│   │   └── setup_knowledge.py    # Base de conocimiento de setups
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── lap_comparator.py     # Comparar vueltas sector a sector
│   │   ├── pattern_detector.py   # Detectar patrones recurrentes
│   │   ├── tyre_model.py         # Modelo degradacion neumaticos
│   │   ├── engine_monitor.py     # Monitor temperaturas motor
│   │   ├── handling_scorer.py    # Clasificar over/understeer, estabilidad
│   │   └── session_report.py     # Generador informe post-sesion
│   ├── ml/
│   │   ├── __init__.py
│   │   ├── corner_predictor.py   # Prediccion tiempo por curva
│   │   ├── tyre_degradation.py   # Modelo predictivo desgaste
│   │   ├── optimal_lap.py        # Calculadora vuelta optima teorica
│   │   ├── setup_behavior.py     # Modelo setup → comportamiento
│   │   ├── training/
│   │   │   ├── __init__.py
│   │   │   ├── feature_engineering.py  # Extraccion de features
│   │   │   ├── train_corner.py   # Entrenamiento corner predictor
│   │   │   ├── train_tyre.py     # Entrenamiento tyre model
│   │   │   └── train_setup.py    # Entrenamiento setup model
│   │   └── models/               # Modelos serializados (.joblib)
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── context_builder.py    # Telemetria → contexto LLM
│   │   ├── copilot_client.py     # Cliente GitHub Copilot API
│   │   ├── ollama_client.py      # Cliente Ollama
│   │   ├── advisor.py            # Orquestador de recomendaciones
│   │   └── prompts/
│   │       ├── system.md         # System prompt del ingeniero
│   │       ├── realtime.md       # Template feedback en vivo
│   │       ├── deep_analysis.md  # Template analisis post-sesion
│   │       ├── race_strategy.md  # Template para modo carrera
│   │       └── setup_advisor.md  # Template para recomendaciones setup
│   ├── voice/
│   │   ├── __init__.py
│   │   ├── voice_manager.py      # Orquestador principal de voz
│   │   ├── stt_engine.py         # faster-whisper STT
│   │   ├── tts_engine.py         # Piper TTS / Edge TTS
│   │   ├── vad.py                # Silero VAD (Voice Activity Detection)
│   │   ├── intent_router.py      # Clasificar intenciones del piloto
│   │   ├── audio_io.py           # Captura/reproduccion de audio
│   │   └── conversation.py       # Gestion contexto conversacional
│   ├── strategy/
│   │   ├── __init__.py
│   │   ├── session_detector.py   # Auto-detectar Practice/Quali/Race
│   │   ├── mode_manager.py       # Gestionar cambios de modo
│   │   ├── practice_mode.py      # Logica modo practica
│   │   ├── quali_mode.py         # Logica modo clasificacion
│   │   ├── race_mode.py          # Logica modo carrera
│   │   ├── fuel_strategy.py      # Calculo combustible
│   │   ├── pit_strategy.py       # Estrategia de paradas
│   │   ├── gap_manager.py        # Gestion de brechas con rivales
│   │   └── tyre_strategy.py      # Estrategia de neumaticos
│   ├── setup_lab/
│   │   ├── __init__.py
│   │   ├── digital_twin.py       # Motor de simulacion fisico
│   │   ├── what_if.py            # Simulador "que pasaria si..."
│   │   ├── driver_profile.py     # Perfil del piloto (consistencia, limites)
│   │   ├── consistency_scorer.py # Evaluador de consistencia
│   │   ├── recommendation.py     # Motor de recomendaciones (consistency-aware)
│   │   └── setup_io.py           # Leer/escribir archivos setup AC
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── influx_client.py      # Cliente InfluxDB async
│   │   ├── sqlite_client.py      # SQLite para metadata
│   │   └── schemas.py            # Esquemas de datos
│   └── dashboard/
│       ├── __init__.py
│       ├── api.py                # FastAPI routes
│       ├── websocket.py          # WebSocket handlers
│       └── deps.py               # Dependency injection
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── TelemetryGauges.tsx
│   │   │   ├── LapComparison.tsx
│   │   │   ├── AIRecommendations.tsx
│   │   │   ├── TrackMap.tsx
│   │   │   ├── TyreMonitor.tsx
│   │   │   ├── SessionProgress.tsx
│   │   │   ├── VoiceStatus.tsx       # Estado de voz
│   │   │   ├── StrategyPanel.tsx     # Panel de estrategia
│   │   │   ├── SetupLab.tsx          # Interfaz del Setup Lab
│   │   │   └── RaceOverview.tsx      # Vista general de carrera
│   │   ├── hooks/
│   │   │   ├── useWebSocket.ts
│   │   │   ├── useTelemetry.ts
│   │   │   └── useVoice.ts
│   │   └── utils/
├── ac_app/                        # App Python para AC (Fase 4+)
│   └── ai_track_engineer/
│       └── ai_track_engineer.py
├── tests/
│   ├── test_shm_reader.py
│   ├── test_lap_segmenter.py
│   ├── test_corner_detector.py
│   ├── test_track_parser.py
│   ├── test_lap_comparator.py
│   ├── test_context_builder.py
│   ├── test_voice_manager.py
│   ├── test_intent_router.py
│   ├── test_session_detector.py
│   ├── test_corner_predictor.py
│   ├── test_digital_twin.py
│   ├── test_consistency_scorer.py
│   └── test_setup_recommendation.py
└── scripts/
    ├── mock_telemetry.py          # Simular SHM para desarrollo sin AC
    ├── export_session.py          # Exportar sesion a CSV/JSON
    ├── train_models.py            # Script entrenamiento ML
    └── parse_car.py               # Utility para parsear archivos de coche
```

---

## Datos de Assetto Corsa - Shared Memory

Assetto Corsa expone telemetria en tiempo real mediante tres estructuras de memoria compartida (SHM). A continuacion se definen como dataclasses de Python con todos los campos relevantes.

### Physics (`acpmf_physics`) — Actualizacion: 60 Hz

```python
from dataclasses import dataclass, field

@dataclass
class ACPhysics:
    """Datos fisicos del coche - actualizados a 60Hz via shared memory."""

    # === Velocidad y Motor ===
    speed_kmh: float              # Velocidad actual en km/h
    rpm: float                    # Revoluciones por minuto del motor
    gear: int                     # Marcha actual: 0=Reversa, 1=Neutral, 2=1a, 3=2a...
    max_rpm: float                # Limite de RPM del motor

    # === Inputs del Piloto ===
    gas: float                    # Posicion acelerador (0.0 = suelto, 1.0 = a fondo)
    brake: float                  # Posicion freno (0.0 = suelto, 1.0 = a fondo)
    clutch: float                 # Posicion embrague (0.0 = suelto, 1.0 = pisado)
    steer_angle: float            # Angulo volante en grados (negativo = izquierda)

    # === Combustible ===
    fuel: float                   # Combustible restante en litros

    # === Fuerzas G ===
    g_force_lateral: float        # Fuerza G lateral (positivo = derecha)
    g_force_longitudinal: float   # Fuerza G longitudinal (positivo = aceleracion)
    g_force_vertical: float       # Fuerza G vertical

    # === Neumaticos - Temperaturas (°C) — 4 ruedas [FL, FR, RL, RR] ===
    tyre_temp_inner: list[float] = field(default_factory=lambda: [0.0]*4)
    tyre_temp_middle: list[float] = field(default_factory=lambda: [0.0]*4)
    tyre_temp_outer: list[float] = field(default_factory=lambda: [0.0]*4)
    tyre_temp_core: list[float] = field(default_factory=lambda: [0.0]*4)

    # === Neumaticos - Presion (PSI) y Desgaste ===
    tyre_pressure: list[float] = field(default_factory=lambda: [0.0]*4)
    tyre_wear: list[float] = field(default_factory=lambda: [0.0]*4)  # 100=nuevo, 0=destruido

    # === Neumaticos - Deslizamiento ===
    tyre_slip_angle: list[float] = field(default_factory=lambda: [0.0]*4)
    tyre_slip_ratio: list[float] = field(default_factory=lambda: [0.0]*4)

    # === Frenos — 4 ruedas [FL, FR, RL, RR] ===
    brake_temp: list[float] = field(default_factory=lambda: [0.0]*4)

    # === Suspension — 4 ruedas [FL, FR, RL, RR] ===
    suspension_travel: list[float] = field(default_factory=lambda: [0.0]*4)

    # === Dano — 5 zonas [frontal, trasero, izq, der, superior] ===
    car_damage: list[float] = field(default_factory=lambda: [0.0]*5)

    # === Motor ===
    engine_temp: float = 0.0      # Temperatura agua (°C)
    oil_temp: float = 0.0         # Temperatura aceite (°C)
    oil_pressure: float = 0.0     # Presion aceite (bar)

    # === Velocidad Vectorial (m/s) ===
    velocity_x: float = 0.0       # Lateral
    velocity_y: float = 0.0       # Vertical
    velocity_z: float = 0.0       # Longitudinal

    # === Velocidad de Ruedas — 4 ruedas (rad/s) ===
    wheel_speed: list[float] = field(default_factory=lambda: [0.0]*4)
```

### Graphics (`acpmf_graphics`) — Actualizacion: Tasa Variable

```python
@dataclass
class ACGraphics:
    """Datos de sesion - tasa de actualizacion variable."""

    # === Estado de Sesion ===
    status: int                   # 0=OFF, 1=REPLAY, 2=LIVE, 3=PAUSE
    session_type: int             # 0=Practice, 1=Qualify, 2=Race

    # === Progreso ===
    completed_laps: int           # Vueltas completadas
    position: int                 # Posicion en carrera (1 = primero)

    # === Tiempos (formato string mm:ss.xxx) ===
    current_time: str             # Tiempo vuelta actual
    last_time: str                # Ultima vuelta completada
    best_time: str                # Mejor tiempo de la sesion

    # === Sectores ===
    current_sector_index: int     # Sector actual: 0, 1 o 2
    last_sector_time: int         # Ultimo sector completado (milisegundos)

    # === Posicion en Pista ===
    normalized_car_position: float  # 0.0 = meta, 1.0 = vuelta completa
    car_coordinates_x: float
    car_coordinates_y: float
    car_coordinates_z: float

    # === Boxes ===
    is_in_pit: bool
    is_in_pit_lane: bool

    # === Condiciones ===
    track_grip_status: int        # 0=Green...6=Flooded
    rain_intensity: int           # 0=None...5=Thunderstorm
```

### Static Info (`acpmf_static`) — Lectura Unica al Inicio

```python
@dataclass
class ACStaticInfo:
    """Datos estaticos - se leen una sola vez al cargar la sesion."""

    car_model: str                # Nombre interno del coche
    track: str                    # Nombre del circuito
    track_config: str             # Configuracion del trazado
    car_skin: str                 # Skin seleccionada

    max_rpm: int                  # RPM maximas
    max_power: int                # Potencia maxima (Watts)
    max_torque: int               # Par maximo (Nm)
    max_fuel: float               # Capacidad tanque (litros)
    gear_count: int               # Numero de marchas

    track_length: float           # Longitud circuito (metros)
    sector_count: int             # Numero de sectores

    num_cars: int                 # Coches en sesion
    pit_window_start: int         # Ventana pit inicio (vuelta)
    pit_window_end: int           # Ventana pit fin (vuelta)
    penalty_enabled: bool         # Penalizaciones activas
```

---

## Datos de Assetto Corsa - Archivos de Fisicas del Coche

El Setup Lab parsea los archivos de datos fisicos del coche ubicados en `content/cars/{car_id}/data/` para construir un modelo fisico (digital twin) que permite simular el efecto de cambios de setup sin necesidad de rodar.

### `power.lut` — Curva de Potencia/Par

| Aspecto | Detalle |
|---------|---------|
| **Formato** | Texto plano con pares `RPM|torque` (uno por linea) |
| **Ubicacion** | `content/cars/{car_id}/data/power.lut` |

```
1000|120.5
2000|205.3
3000|310.7
5000|420.0
7000|438.1
8500|380.0
```

**Uso:** Construir curva potencia/par, determinar powerband, calcular shift points optimos.

### `tyres.ini` — Modelo Termico y Mecanico

| Aspecto | Detalle |
|---------|---------|
| **Formato** | INI con secciones `[FRONT]` `[REAR]` |
| **Ubicacion** | `content/cars/{car_id}/data/tyres.ini` |

**Datos clave:** PERFORMANCE_CURVE (temp→grip), PRESSURE_IDEAL, WEAR_CURVE, DY0/DY1 (slip), CAMBER_GAIN

**Uso:** Rango optimo de temperatura, presion ideal, prediccion de grip, sensibilidad a setup.

### `aero.ini` — Aerodinamica

| Aspecto | Detalle |
|---------|---------|
| **Formato** | INI con secciones `[WING_0]` (front), `[WING_1]` (rear), `[BODY]` |
| **Ubicacion** | `content/cars/{car_id}/data/aero.ini` |

**Datos clave:** CL, CD, ANGLE, MIN/MAX, CHORD, SPAN, FRONTAL_AREA

**Uso:** Calcular downforce/drag vs velocidad, balance aerodinamico, trade-offs de ala.

### `suspensions.ini` — Suspension

| Aspecto | Detalle |
|---------|---------|
| **Formato** | INI con secciones `[FRONT]` `[REAR]` |
| **Ubicacion** | `content/cars/{car_id}/data/suspensions.ini` |

**Datos clave:** SPRING_RATE, BUMP, REBOUND, ROD_LENGTH (ARB), PACKER_RANGE, TOE, CAMBER

**Uso:** Predecir grip mecanico, transferencia de peso, ride height, roll stiffness.

### `drivetrain.ini` — Transmision y Diferencial

| Aspecto | Detalle |
|---------|---------|
| **Formato** | INI |
| **Ubicacion** | `content/cars/{car_id}/data/drivetrain.ini` |

**Datos clave:** TYPE (RWD/FWD/AWD), GEAR ratios, FINAL drive, POWER/COAST lock %, PRELOAD

**Uso:** Velocidad por marcha, comportamiento diff en curvas, traccion.

### `brakes.ini` — Sistema de Frenado

| Aspecto | Detalle |
|---------|---------|
| **Formato** | INI |
| **Ubicacion** | `content/cars/{car_id}/data/brakes.ini` |

**Datos clave:** FRONT_SHARE (bias), MAX_TORQUE, DISC_DIAMETER, PAD_FRICTION

**Uso:** Estabilidad en frenada, bias optimo, temperaturas de disco.

### `car.ini` — Datos Generales

| Aspecto | Detalle |
|---------|---------|
| **Formato** | INI |
| **Ubicacion** | `content/cars/{car_id}/data/car.ini` |

**Datos clave:** TOTAL_MASS, FUEL_CONSUMPTION, FRONT weight distribution

**Uso:** Distribucion de peso, estrategia combustible, balance general.

### Archivos de Setup (`.ini`)

| Aspecto | Detalle |
|---------|---------|
| **Ubicacion** | `content/cars/{car_id}/setup/{track_id}/setup_name.ini` |
| **Contenido** | WING values, PRESSURE, SPRING_RATE, CAMBER, TOE, RIDE_HEIGHT, BRAKE_BIAS, DIFF settings, FUEL |

Estos son los parametros modificables que el Setup Lab recomendara ajustar.

---

## Fases de Implementacion

### Fase 1 - Fundacion (MVP) | ~2-3 semanas

**Objetivo:** Capturar telemetria en vivo y mostrarla en un dashboard web funcional.

**Componentes:** `src/telemetry/`, `src/processing/lap_segmenter.py`, `src/storage/`, `src/dashboard/`, `frontend/` basics, `scripts/mock_telemetry.py`

**Tareas:**

1. Init proyecto Python con `pyproject.toml` (uv como package manager)
2. Implementar `shm_structs.py` con estructuras ctypes de AC shared memory
3. Implementar `shm_reader.py` - lectura async de SHM a 60Hz
4. Crear `models.py` con Pydantic models para validacion
5. Implementar `lap_segmenter.py` - deteccion de cruces de meta usando `normalized_car_position`
6. Configurar `docker-compose.yml` con InfluxDB 2.x
7. Implementar `influx_client.py` - escritura de telemetria por batches
8. Crear `api.py` con FastAPI + WebSocket
9. Implementar `mock_telemetry.py` para desarrollo sin AC
10. Crear React app con Vite - gauges basicos (velocidad, RPM, marcha, inputs, temperaturas)

**Criterio de aceptacion:**

- Dashboard muestra datos en vivo con latencia < 50ms
- Vueltas se detectan y almacenan en InfluxDB
- Tiempos por vuelta con precision de milisegundos

---

### Fase 2 - Motor de Analisis | ~3-4 semanas

**Objetivo:** Analizar rendimiento por curva y comparar vueltas.

**Componentes:** `src/knowledge/track_parser.py`, `src/processing/corner_detector.py`, `src/processing/normalizer.py`, `src/analysis/lap_comparator.py`, `src/analysis/tyre_model.py`, `src/analysis/engine_monitor.py`

**Tareas:**

1. Implementar `track_parser.py`:
   - Parsear `ai_line.bin` (array de puntos 3D con velocidades ideales)
   - Parsear `track.ini` (metadata)
   - Extraer racing line y sectores

2. Implementar `corner_detector.py`:
   - Detectar curvas por cambio de curvatura
   - Definir zonas (approach, turn-in, apex, exit)
   - Asignar IDs unicos a cada curva

3. Implementar `normalizer.py`:
   - Normalizar por distancia recorrida
   - Interpolar para comparacion uniforme

4. Implementar `lap_comparator.py`:
   - Delta acumulado entre vueltas
   - Diferencias por sector y curva
   - Detectar donde se gana/pierde tiempo

5. Implementar `tyre_model.py`:
   - Ventana optima por compuesto
   - Detectar sobre/subcalentamiento
   - Balance termico (inner/middle/outer)

6. Implementar `engine_monitor.py`:
   - Alertas temperatura agua/aceite
   - Deteccion over-rev

7. Actualizar dashboard:
   - Comparacion vueltas overlay
   - Delta bar real-time
   - Mapa circuito con zonas coloreadas
   - Monitor neumaticos visual

**Criterio de aceptacion:**

- Identifica correctamente todas las curvas del circuito
- Comparacion precisa con delta por curva
- Alertas funcionales de temperatura

---

### Fase 3 - Integracion IA | ~2-3 semanas

**Objetivo:** Generar recomendaciones inteligentes en lenguaje natural post-vuelta.

**Componentes:** `src/ai/` (`context_builder`, `copilot_client`, `ollama_client`, `advisor`, `prompts/`)

**Tareas:**

1. Implementar `context_builder.py`:
   - Resumir vuelta en texto estructurado para LLM
   - Incluir tiempos/delta/inputs/temps
   - Formato eficiente en tokens (tabular)
   - Priorizar info relevante

2. Implementar `copilot_client.py`:
   - Auth GitHub Copilot API
   - Llamadas async con retry/rate limiting
   - Streaming de respuestas

3. Implementar `ollama_client.py`:
   - Misma interfaz (Protocol/ABC)
   - Deteccion automatica de disponibilidad
   - Configuracion de modelo

4. Disenar `prompts/`:
   - `system.md` (personalidad ingeniero)
   - `realtime.md` (feedback rapido)
   - `deep_analysis.md` (analisis completo)

5. Implementar `advisor.py`:
   - Orquestar cuando pedir recomendaciones (fin vuelta, anomalia, solicitud)
   - Historial conversacion por sesion
   - Fallback Copilot → Ollama

6. Dashboard:
   - Panel de recomendaciones
   - Historial de consejos
   - Indicador de prioridad

**System Prompt Base (`prompts/system.md`):**

```markdown
Eres un ingeniero de pista profesional con 20 anos de experiencia en GT3, GTE y Formula
regional. Tu piloto depende de ti para mejorar sus tiempos.

REGLAS:
- Se CONCISO. Maximo 2-3 frases por recomendacion.
- PRIORIZA cambios que ahorren mas tiempo. Siempre indica el delta estimado.
- Usa TERMINOLOGIA correcta de racing: trail braking, understeer, oversteer, rotation,
  apex, track-out, traction zone, lift-off, threshold braking, weight transfer.
- NUNCA des consejos genericos. Siempre referencia la curva especifica (por nombre o numero),
  la velocidad concreta y el punto exacto.
- Si no tienes suficientes datos para un consejo concreto, NO inventes. Di que necesitas
  mas vueltas.
- Adapta la agresividad del consejo al nivel del piloto.
- Formato: "[Curva X] Accion concreta → resultado esperado (delta estimado)"
- Prioridad: 1) Frenadas 2) Trazada 3) Throttle application 4) Consistencia
```

**Criterio de aceptacion:**

- Tras cada vuelta genera 2-4 recomendaciones relevantes y especificas
- Fallback a Ollama transparente si Copilot no esta disponible
- Recomendaciones referencian curvas especificas con datos concretos

---

### Fase 4 - Feedback en Tiempo Real | ~3-4 semanas

**Objetivo:** Feedback durante la conduccion, no solo post-vuelta.

**Componentes:** `src/processing/delta.py` (extended), `src/ai/advisor.py` (real-time mode), `src/dashboard/websocket.py` (priority queue)

**Tareas:**

1. Sistema de prediccion de frenado:
   - Comparar posicion/velocidad actual vs mejor vuelta
   - Avisar X metros antes del punto de frenado ideal
   - Indicador visual de "brake zone approaching"

2. Corner coach en vivo:
   - Al salir de cada curva comparar inmediatamente vs referencia
   - Feedback instantaneo ("+0.2s T5 - entrada tarde")
   - Acumular contexto para no repetir el mismo consejo

3. Filtro inteligente:
   - Threshold configurable por piloto
   - No interrumpir en zonas de alta carga cognitiva
   - Priorizar solo el consejo mas importante
   - Cooldown entre mensajes

4. Cola de mensajes priorizada:
   - **Urgente:** temperaturas criticas, banderas
   - **Alta:** consejo frenado/trazada para curva proxima
   - **Normal:** feedback post-curva
   - **Baja:** observaciones generales

5. Dashboard real-time:
   - Notificaciones toast con auto-dismiss
   - Indicador de proxima accion sugerida
   - Mini timeline con marcadores de feedback

**Criterio de aceptacion:**

- Feedback llega antes de entrar en la curva relevante
- No satura al piloto (max 1 mensaje cada 5-8 segundos)
- Latencia total del pipeline < 100ms

---

### Fase 5 - Analisis Avanzado | ~3-4 semanas

**Objetivo:** Analisis profundo con ML basico, reportes de sesion y tracking de progreso a largo plazo.

**Componentes:** `src/analysis/pattern_detector.py`, `src/analysis/session_report.py`, `src/storage/` (progress tracking queries)

**Tareas:**

1. Pattern Detector:
   - Clustering + anomaly detection sobre historico de vueltas
   - Detectar patrones recurrentes ("siempre pierdes en frenadas >100m")
   - Detectar regresiones ("trazada T7 empeorada ultimas 3 sesiones")
   - Correlaciones (temp neumaticos → perdida de tiempo en sector)

2. Session Report Generator:
   - Informe completo post-sesion con graficos
   - Evolucion de tiempos durante la sesion
   - Consistencia por sector (desviacion estandar)
   - Comparativa primera vs ultima vuelta
   - Exportable a PDF/HTML

3. Progress Tracker:
   - Evolucion del piloto semana/mes
   - Mejores tiempos historicos por circuito/coche
   - Areas de mejora sostenida vs areas estancadas
   - Mensajes con datos: "Has mejorado 1.2s en Spa en las ultimas 5 sesiones, principalmente en sector 2"

4. Multi-car comparison:
   - Perfil por coche (puntos fuertes/debiles del piloto con cada vehiculo)
   - Recomendacion de que practicar segun el coche elegido
   - Deteccion de skills transferibles entre coches

**Criterio de aceptacion:**

- Detecta al menos 3 tipos de patrones recurrentes
- Reportes generados automaticamente al finalizar sesion
- Tracking historico funcional con graficos de tendencia

---

### Fase 6 - Voz Bidireccional | ~3-4 semanas

**Objetivo:** Comunicacion por voz natural entre piloto e ingeniero — el piloto puede hablar mientras conduce y el ingeniero responde por audio.

**Componentes:** `src/voice/` (voice_manager, stt_engine, tts_engine, vad, intent_router, audio_io, conversation), `config/voice/`

**Tareas:**

1. Implementar `audio_io.py`:
   - Captura microfono con `sounddevice` (menor latencia que PyAudio)
   - Buffer circular de audio entrante (ultimos 30s)
   - Reproduccion audio TTS con gestion de cola
   - Sample rate: 16kHz mono para STT, 22050Hz para TTS output

2. Implementar `vad.py`:
   - Silero VAD como motor principal (~2ms por frame)
   - Filtrado ruido ambiente (ruido pedales/volante)
   - Threshold adaptativo segun nivel ruido medido
   - Dos modos: Push-to-talk (boton volante) O deteccion automatica
   - Pre-buffer: capturar 300ms antes de deteccion para no perder inicio

3. Implementar `stt_engine.py`:
   - Motor: `faster-whisper` para transcripcion local
   - Modelos: `small` (rapido ~2s) y `medium` (preciso ~4s)
   - Transcripcion en streaming (parcial mientras habla)
   - Idioma configurable (ES/EN)
   - Vocabulario personalizado: "box", "pit", "undercut", nombres de curvas

4. Implementar `intent_router.py`:
   - Clasificar intencion del piloto:
     - QUERY: "como estoy en sector 2?" → respuesta informativa
     - COMMAND: "cambiar a modo carrera" → accion del sistema
     - FEEDBACK: "la curva 3 se siente inestable" → registrar
     - CONFIRMATION: "si/no/entendido" → confirmar accion previa
     - CONVERSATION: "que me recomiendas?" → consulta libre al LLM

   ```python
   class Intent(Enum):
       QUERY = "query"
       COMMAND = "command"
       FEEDBACK = "feedback"
       CONFIRMATION = "confirmation"
       CONVERSATION = "conversation"

   @dataclass
   class ParsedIntent:
       intent: Intent
       entities: dict[str, Any]  # {"sector": 2, "corner": 3, "mode": "race"}
       confidence: float
       raw_text: str
   ```

   - Pattern matching primero (latencia ~1ms), LLM como fallback si confianza baja

5. Implementar `tts_engine.py`:
   - Motor primario: Piper TTS (local, latencia ~200ms)
   - Motor fallback: Edge TTS (cloud, mas natural)
   - Cola con prioridad: CRITICAL > HIGH > NORMAL > LOW
   - Velocidad de habla ajustable (mas rapida en carrera)
   - Cache de frases comunes pre-generadas ("Box box box", "Bien hecho")
   - Chunking: dividir mensajes largos para inicio de reproduccion rapido

6. Implementar `voice_manager.py`:
   - Pipeline: VAD → STT → Intent → [LLM si necesario] → TTS
   - Maquina de estados: IDLE, LISTENING, PROCESSING, SPEAKING
   - Interrupcion: si piloto habla mientras TTS activo → cortar TTS, escuchar
   - Coordinacion con dashboard: mensajes voz se reflejan como texto en UI
   - Rate limiting entre mensajes no criticos

7. Implementar `conversation.py`:
   - Contexto de ultimas N interacciones (ventana deslizante)
   - Enriquecer respuestas con datos actuales de telemetria
   - Personalidad consistente segun modo de sesion
   - Resolucion de referencias: "y ahi?" → ultima curva mencionada

**Criterio de aceptacion:**

- Latencia end-to-end (fin habla → inicio TTS) < 1.5 segundos
- Reconocimiento de intenciones > 90% en 100 frases comunes
- Push-to-talk funcional + modo deteccion automatica
- Override de modo por voz funcional
- TTS conciso (< 8 segundos en carrera)
- Interrupcion funciona (TTS se corta al hablar el piloto)
- CPU usage pipeline voz < 15% en un core

---

### Fase 7 - Modelos Predictivos ML | ~4-5 semanas

**Objetivo:** Modelos de machine learning que predicen rendimiento y aprenden del estilo especifico del piloto.

**Componentes:** `src/ml/` (corner_predictor, tyre_degradation, optimal_lap, setup_behavior, training/)

**Tareas:**

1. Feature Engineering (`training/feature_engineering.py`):
   - Features por curva: velocidad entrada/apex/salida, punto frenado, trail braking %, tiempo throttle, angulo volante max, g lateral max, slip angles
   - Features por vuelta: consistencia sectores, varianza inputs, degradacion progresiva
   - Features de setup: camber, presion, springs, aero balance, ride height, diff
   - Normalizacion Z-score por pista, deteccion outliers (IQR), rolling features (tendencia ultimas 5 vueltas)

2. Corner Time Predictor (`corner_predictor.py`):
   - Input: features entrada a curva (velocidad, marcha, posicion)
   - Output: tiempo estimado para esa curva
   - Modelo: XGBoost Regressor con historico del piloto
   - Aplicacion: "Si frenaras 5m mas tarde en T3, ganarias ~0.15s"

   ```python
   class CornerPredictor:
       def predict_corner_time(
           self, corner_id: int, entry_speed: float,
           brake_point: float, gear: int
       ) -> PredictionResult:
           """Predice el tiempo en una curva dados los inputs de entrada."""
           ...

       def suggest_improvement(
           self, corner_id: int, current_inputs: CornerInputs
       ) -> list[Suggestion]:
           """Sugiere cambios en inputs para mejorar tiempo."""
           ...
   ```

3. Tyre Degradation Model (`tyre_degradation.py`):
   - Input: vuelta actual, temperaturas, presiones, estilo conduccion (agresividad slip)
   - Output: grip restante por rueda, vueltas hasta caida de rendimiento
   - Modelo: time-series regression con features de driving style
   - Aplicacion: "Al ritmo actual, traseros perderan grip en ~8 vueltas"
   - Diferenciar degradacion termica (reversible) vs superficial (irreversible)

4. Optimal Lap Calculator (`optimal_lap.py`):
   - Combinar mejores parciales por curva del piloto
   - Constraint: parciales deben ser fisicamente compatibles (velocidad salida N = entrada N+1)
   - Usar percentil 90 (no mejor absoluto) para objetivos alcanzables
   - Identificar "low-hanging fruit": curvas con mayor margen vs propio potencial

5. Setup → Behavior Model (`setup_behavior.py`):
   - Input: vector numerico de setup (20-30 dimensiones)
   - Output: understeer tendency, oversteer_on_power, braking_stability, traction, top_speed_delta
   - Minimo 10 setups distintos para predicciones utiles
   - Aplicacion: "Con +1 click ala trasera: +0.3s sector 1, -0.5s sector 2 (neto -0.2s)"

   ```python
   class SetupBehaviorModel:
       def predict_behavior(self, setup: SetupVector) -> BehaviorPrediction:
           """Predice comportamiento del coche con un setup dado."""
           ...

       def compare_setups(
           self, setup_a: SetupVector, setup_b: SetupVector
       ) -> SetupComparison:
           """Compara dos setups y predice diferencias."""
           ...
   ```

6. Training Pipeline (`scripts/train_models.py`):
   - Extraccion desde InfluxDB automatizada
   - Split temporal (NO random) para evitar data leakage
   - Cross-validation por sesion
   - Metricas: MAE, R2, feature importance
   - Re-entrenamiento incremental con datos nuevos
   - Model registry con versionado y rollback automatico

**Criterio de aceptacion:**

- Corner predictor con MAE < 0.1s por curva tras 50+ vueltas
- Tyre model predice degradacion con ±2 vueltas de precision
- Optimal lap genera vuelta fisicamente coherente
- Setup model muestra correlaciones correctas (mas ala = mas grip + mas drag)
- Training pipeline ejecuta end-to-end sin intervencion
- Feature importance es interpretable y coherente con fisica

---

### Fase 8 - Estratega de Carrera | ~3-4 semanas

**Objetivo:** Adaptar comportamiento segun tipo de sesion (Practice/Quali/Race) con estrategia activa en carrera.

**Componentes:** `src/strategy/` (session_detector, mode_manager, practice_mode, quali_mode, race_mode, fuel_strategy, pit_strategy, gap_manager, tyre_strategy)

**Tareas:**

1. Implementar `session_detector.py`:
   - Leer `session_type` de ACGraphics (0=Practice, 1=Qualify, 2=Race)
   - Auto-detectar al inicio de sesion
   - Permitir override por voz: "Ingeniero, cambia a modo clasificacion"
   - Detectar cambios en servidor online

2. Implementar `mode_manager.py`:
   - Gestionar transiciones limpias entre modos
   - Ajustar personalidad/prioridades del AI segun modo
   - Configurar datos visibles en dashboard segun modo
   - Notificar: "Modo carrera activado. Combustible para 22 vueltas."

3. Implementar `practice_mode.py`:
   - PRIORIDAD: Aprendizaje y experimentacion
   - Personalidad: Paciente, explicativa, exploradora
   - Analisis detallado cada vuelta, sugerencias de experimentacion
   - Tracking de variantes probadas, NO presionar por tiempos
   - Detectar "modo consistencia" vs "modo exploracion" del piloto

4. Implementar `quali_mode.py`:
   - PRIORIDAD: Vuelta perfecta unica
   - Personalidad: Precisa, enfocada, minimalista
   - Monitorear temps/presiones, gestionar outlap, crear gap
   - Durante hot lap: SILENCIO (solo alertas criticas)
   - Abort si error significativo en S1
   - Flujo: `[Outlap] "Neumaticos 94%. Push proxima." → [Hot lap] silencio → [Post] "1:42.1 PB!"`

5. Implementar `race_mode.py`:
   - PRIORIDAD: Resultado final (posicion)
   - Personalidad: Tactica, calmada, decisiva
   - Comunicacion tipo F1: gaps, ritmo, defensa/ataque
   - Fases: salida (agresiva), media (gestion), final (push si necesario)
   - Coordinar con fuel/tyre/pit strategies

6. Implementar `fuel_strategy.py`:
   - Consumo por vuelta (promedio movil ultimas 5)
   - Prediccion combustible al final
   - Alertas: INFO → WARNING → CRITICAL
   - Fuel saving con ubicacion: "Lift and coast T8-T9"
   - Calculo carga optima inicial (peso vs tiempo)

7. Implementar `pit_strategy.py`:
   - Ventana optima basada en degradacion + posiciones
   - Undercut/overcut analysis
   - Comunicacion anticipada: 3 vueltas antes → 1 vuelta → "Box box box"
   - Recalcular si condiciones cambian

8. Implementar `gap_manager.py`:
   - Tracking gaps adelante/atras (datos AC shared memory)
   - Tendencia: gap se cierra/abre/estable (ultimas 5 vueltas)
   - Alertas: "Coche atras cerrando 0.3s/vuelta. Contacto en ~4 vueltas"
   - Target lap time para mantener/cerrar posicion

9. Implementar `tyre_strategy.py`:
   - Integracion con ML degradation model (Fase 7)
   - Decision cambio vs mantener (tiempo pit vs tiempo perdido)
   - Ritmo objetivo para preservar neumaticos
   - Planes adaptativos: "Plan B: conservar traseros, atacar ultimas 5 vueltas"

**Criterio de aceptacion:**

- Deteccion automatica correcta en 100% de casos
- Override por voz funcional y confirmado
- Cada modo con personalidad claramente diferenciada
- Estrategia combustible con error < 0.5L al final
- Pit window coherente con estado neumaticos
- Max 1 mensaje cada 30s en carrera (excepto critico)
- Transicion entre modos < 1s

---

### Fase 9 - Setup Lab (Digital Twin) | ~5-6 semanas

**Objetivo:** Laboratorio de setup basado en fisica que recomienda configuraciones optimizadas para el PILOTO ESPECIFICO, priorizando consistencia sobre velocidad pura teorica.

**Filosofia clave:**

> El mejor setup NO es el teoricamente mas rapido, sino el mas rapido que el piloto puede ejecutar CONSISTENTEMENTE. Ejemplo: 0 aleron en Monza es teoricamente optimo, pero si causa spins, un setup con algo mas de aleron que permita vueltas consistentes es MEJOR.

**Componentes:** `src/knowledge/car_physics/` (parsers), `src/setup_lab/` (digital_twin, what_if, driver_profile, consistency_scorer, recommendation, setup_io)

**Tareas:**

1. Implementar Car Physics Parsers (`src/knowledge/car_physics/`):
   - `power_parser.py`: parsear power.lut, curva potencia/par, shift points
   - `tyre_parser.py`: parsear tyres.ini, modelo termico (temp→grip), slip curves, camber sensitivity
   - `aero_parser.py`: parsear aero.ini, downforce/drag vs speed por configuracion de ala
   - `suspension_parser.py`: parsear suspensions.ini, rigidez roll, transferencia peso
   - `drivetrain_parser.py`: parsear drivetrain.ini, ratios, diff behavior
   - `brake_parser.py`: parsear brakes.ini, bias efectivo, potencia frenado
   - `car_model.py`: modelo unificado combinando todos los parsers

   ```python
   class CarPhysicsModel:
       def downforce_at_speed(self, speed_ms: float, wing_angles: WingConfig) -> Force:
           """Calcula downforce total a una velocidad con config de alas dada."""
           ...

       def weight_transfer(self, lateral_g: float, longitudinal_g: float) -> WheelLoads:
           """Calcula transferencia de peso por rueda."""
           ...

       def tyre_grip(self, temp: float, pressure: float, load: float) -> float:
           """Calcula grip disponible para condiciones dadas."""
           ...

       def optimal_shift_point(self, current_gear: int) -> int:
           """RPM optimo para cambiar de marcha."""
           ...

       def max_cornering_speed(self, radius: float, wing_angles: WingConfig,
                               tyre_temp: float, tyre_pressure: float) -> float:
           """Velocidad maxima en curva dado radio y condiciones."""
           ...
   ```

2. Implementar `driver_profile.py`:
   - Construir perfil cuantitativo del piloto desde historico:

   ```python
   @dataclass
   class DriverProfile:
       oversteer_tolerance: float      # 0.0 (nada) - 1.0 (experto drift)
       brake_consistency: float        # Varianza en metros del punto de frenado
       aggression_level: float         # 0.0 (conservador) - 1.0 (al limite)
       input_smoothness: float         # 0.0 (brusco) - 1.0 (suave)
       stability_preference: float     # Cuanto valora estabilidad vs velocidad
       corner_types: dict[str, float]  # {"high_speed": 0.85, "low_speed": 0.92}
   ```

   - Actualizar continuamente con cada sesion (exponential moving average)
   - Detectar mejoras del piloto a lo largo del tiempo

3. Implementar `consistency_scorer.py`:
   - Evaluar consistencia del piloto CON un setup dado:
     - Varianza tiempos por vuelta (σ)
     - Frecuencia errores (spins, track limits, lockups)
     - Degradacion de rendimiento durante stint
     - Porcentaje vueltas "limpias"
   - Un setup con mejor tiempo pero peor consistencia puede ser PEOR overall

   ```python
   @dataclass
   class ConsistencyScore:
       overall: float                  # 0-1 (1 = perfectamente consistente)
       lap_time_variance: float        # σ en segundos
       error_rate: float               # errores por vuelta
       clean_lap_percentage: float     # 0-1
       per_corner_scores: dict[int, float]
   ```

4. Implementar `digital_twin.py`:
   - Motor simulacion punto-masa enriquecido (NO replica AC, solo captura efectos principales)
   - Calcula por sector/curva:
     - Velocidad maxima en curva: dado grip + aero + peso + radio
     - Distancia frenado: dado peso + aero + grip + bias
     - Aceleracion salida: dado traccion + potencia + diff
     - Velocidad punta recta: dado potencia vs drag
   - Calibracion con datos reales (factores correccion)
   - Resolucion: por segmento de pista, no frame-by-frame

5. Implementar `what_if.py`:
   - Simulador "que pasaria si cambio X":

   ```python
   @dataclass
   class WhatIfResult:
       predicted_laptime_delta: float   # Positivo = mas lento
       sector_deltas: list[float]
       consistency_impact: float        # Positivo = mas consistente
       confidence: float                # 0-1
       explanation: str
       risk_assessment: str             # "Bajo riesgo" / "Riesgo medio" / "Alto"

   class WhatIfSimulator:
       def simulate_change(
           self, current_setup: SetupVector, change: SetupChange,
           track: TrackModel, driver: DriverProfile
       ) -> WhatIfResult:
           """
           1. Aplicar cambio al modelo fisico
           2. Recalcular limites por curva
           3. Ajustar por perfil piloto (puede aprovechar el cambio?)
           4. Calcular impacto en consistencia
           5. Generar explicacion y evaluacion de riesgo
           """
           ...
   ```

6. Implementar `recommendation.py` (Consistency-Aware Recommender):
   - Pipeline:
     1. Detectar problemas de handling (oversteer T5, understeer T2, inestabilidad frenada T8)
     2. Generar cambios candidatos para cada problema
     3. Simular cada cambio con what_if
     4. Filtrar: rechazar cambios que empeoran consistencia
     5. Rankear por: `score = time_gain × (1 + consistency_improvement) × driver_compatibility`
     6. Presentar top 3 con explicacion completa

   - Ejemplo de recomendacion:
   ```
   RECOMENDACION #1 (score: 0.87, confianza: alta)
   Cambio: Ala trasera +2 clicks (de 5 a 7)
   Efecto: -0.4s/vuelta (ganas en S2 curvas, pierdes 0.1s en recta S1)
   Consistencia: MEJORA (+15% menos varianza en T5-T8)
   Razon: Tu perfil muestra problemas de traccion en salida de curvas lentas.
   Mas ala trasera estabiliza el tren trasero donde mas lo necesitas.
   Riesgo: Bajo. Pierdes velocidad punta pero ganas donde pierdes mas.
   ```

7. Implementar `setup_io.py`:
   - Leer/escribir archivos .ini de setup de AC
   - Validar rangos (NUNCA recomendar fuera de lo permitido)
   - Backup automatico antes de modificar
   - El piloto puede decir "aplica recomendacion 1"

**Criterio de aceptacion:**

- Parsers extraen datos correctamente de al menos 10 coches diferentes
- Digital twin predice direccion correcta (mas ala = mas grip curva + mas drag)
- Consistency scorer correlaciona con rendimiento real (R2 > 0.7)
- Recomendaciones priorizan efectivamente consistencia sobre velocidad pura
- What-if predictions dentro de ±0.3s tras calibracion
- Setup IO hace backup SIEMPRE antes de modificar
- Pipeline completo (detectar → recomendar → aplicar) < 10 segundos

---

## Comportamiento por Tipo de Sesion

El sistema adapta completamente su personalidad, prioridades y estilo de comunicacion segun el tipo de sesion activa.

| Aspecto | Practice | Qualifying | Race |
|---|---|---|---|
| Prioridad | Aprendizaje | Vuelta perfecta | Resultado final |
| Personalidad | Paciente, explorador | Precisa, enfocada | Tactica, decisiva |
| Feedback freq | Alto (cada vuelta) | Minimo (no distraer) | Medio (gaps, strategy) |
| Analisis depth | Maximo detalle | Solo vs mejor tiempo | Relativo a rivales |
| Voz | Explicativa, larga | Concisa, pre/post lap | Tipo radio F1 |
| Neumaticos | Experimentar limites | Ventana optima push | Gestion para distancia |
| Errores | Oportunidad aprender | "Aborta, resetea" | "Recupera, minimiza dano" |

### Modo Practice

El ingeniero es un **profesor**. Fomenta experimentacion, da explicaciones detalladas, lleva registro de variantes probadas, nunca presiona por tiempos.

- *"Intenta frenar 5 metros mas tarde en T3, veamos que pasa"*
- *"Esa linea alternativa en T7 funciono: +0.1s ahi pero -0.3s en salida"*
- *"Llevas 8 vueltas sin probar trail braking largo en T1. Quieres intentar?"*

### Modo Qualifying

El ingeniero es un **cirujano**. Comunicacion minima durante hot laps. Prepara condiciones perfectas y luego se aparta.

- *[Outlap] "Neumaticos al 94%. Push proxima."*
- *[Hot lap] silencio total*
- *[Cooldown] "1:42.1 nuevo PB! S2 excelente, margen en T11 aun."*
- *[Abort] "Trafico S1. Aborta. Cooldown y reintentamos."*

### Modo Race

El ingeniero es un **estratega**. Gestiona la imagen completa: gaps, combustible, neumaticos, pit windows, defensa/ataque. Comunicacion tipo radio F1.

- *"Vuelta 12/25. Gap delante 2.1s estable. Traseros al 68%. Box vuelta 15 si ritmo cae."*
- *"Coche detras 0.5s mas rapido ultimo sector. Cuida interior T1."*
- *"Undercut posible: box ahora, sale con 1.5s margen limpio."*

### Auto-deteccion + Override

- Sistema lee `session_type` de shared memory automaticamente
- Override por voz: "Modo clasificacion" / "Modo carrera" / "Modo practica"
- Override persiste hasta cambio explicito del piloto o cambio de sesion en AC
- Transiciones generan confirmacion: "Entendido, cambio a modo carrera."

---

## Consideraciones Tecnicas

### Rendimiento

- **SHM Reading:** Usar `mmap` directo, leer solo campos necesarios segun contexto actual.
- **Buffer circular:** Ultimos 600 frames (10s a 60Hz) en memoria sin hit a DB.
- **Batch writes:** InfluxDB en batches de 100-500 puntos. Flush forzado al fin de vuelta.
- **WebSocket throttle:** 20-30Hz al frontend. Interpolar en frontend si se quiere animacion suave.
- **Voice pipeline:** STT en thread separado, no bloquear telemetry loop. Queue asincrona entre capas.
- **ML inference:** Modelos pre-cargados, target < 5ms. Si excede 20ms, degradar a heuristica.

### Rate Limiting IA

- NO llamar al LLM cada frame. Triggers: fin vuelta, fin curva si delta>threshold, anomalia, solicitud piloto.
- Cache de respuestas similares.
- Token budget: limite configurable por sesion (default 50k tokens).
- En modo carrera: reducir llamadas LLM, usar logica determinista para gaps/estrategia.

### Desarrollo sin AC

- `mock_telemetry.py`: reproduccion a velocidad real o acelerada (2x/5x/10x), errores programaticos, simular multiples coches, loop continuo.
- Mock voice input: archivo de comandos con timestamps para testing STT.

### Gestion de Errores

| Escenario | Respuesta |
|---|---|
| AC crash/cierre | Reconexion automatica SHM, retry exponencial, preservar estado |
| Perdida conexion IA | Queue pendientes, funcionar con heuristicas |
| InfluxDB caida | Buffer memoria (max 10k puntos), flush cuando vuelva |
| Microfono desconectado | Fallback dashboard-only, notificar visualmente |
| ML model corrupto | Heuristicas como fallback, log error |
| Datos telemetria invalidos | Descartar frame, alertar si persiste >1s |

### ML Model Lifecycle

- Re-entrenamiento cada 10 sesiones (configurable)
- Versionado con fecha, hash datos, metricas
- Rollback automatico si predicciones empeoran
- Cold start: primeras sesiones usan heuristicas, ML se activa con datos suficientes (min 5 sesiones por circuito/coche)
- Modelos especificos por combinacion coche+circuito

---

## Docker Compose

```yaml
version: '3.8'

services:
  influxdb:
    image: influxdb:2.7
    ports:
      - "8086:8086"
    environment:
      - DOCKER_INFLUXDB_INIT_MODE=setup
      - DOCKER_INFLUXDB_INIT_USERNAME=admin
      - DOCKER_INFLUXDB_INIT_PASSWORD=ai-track-engineer
      - DOCKER_INFLUXDB_INIT_ORG=ai-track-engineer
      - DOCKER_INFLUXDB_INIT_BUCKET=telemetry
      - DOCKER_INFLUXDB_INIT_RETENTION=90d
    volumes:
      - influxdb-data:/var/lib/influxdb2
      - influxdb-config:/etc/influxdb2

  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama-data:/root/.ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  api:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - INFLUXDB_URL=http://influxdb:8086
      - INFLUXDB_TOKEN=${INFLUXDB_TOKEN}
      - INFLUXDB_ORG=ai-track-engineer
      - INFLUXDB_BUCKET=telemetry
      - COPILOT_API_KEY=${COPILOT_API_KEY}
      - OLLAMA_URL=http://ollama:11434
    depends_on:
      - influxdb
      - ollama
    volumes:
      - ./config:/app/config
      - ./src/ml/models:/app/models

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    depends_on:
      - api

volumes:
  influxdb-data:
  influxdb-config:
  ollama-data:
```

---

## Dependencias Python

```toml
[project]
name = "ai-track-engineer"
version = "0.1.0"
requires-python = ">=3.12"

dependencies = [
    # Core
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "websockets>=13.0",
    "pydantic>=2.9.0",
    "pydantic-settings>=2.5.0",

    # Data Processing
    "numpy>=2.0.0",
    "pandas>=2.2.0",
    "scipy>=1.14.0",

    # Storage
    "influxdb-client[async]>=1.44.0",
    "aiosqlite>=0.20.0",

    # AI
    "httpx>=0.27.0",
    "ollama>=0.3.0",

    # Voice
    "faster-whisper>=1.0.0",
    "piper-tts>=1.2.0",
    "edge-tts>=6.1.0",
    "silero-vad>=4.0.0",
    "sounddevice>=0.4.7",

    # ML
    "scikit-learn>=1.5.0",
    "xgboost>=2.1.0",
    "joblib>=1.4.0",

    # Utils
    "structlog>=24.4.0",
    "pyyaml>=6.0.0",
    "typer>=0.12.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=5.0.0",
    "ruff>=0.6.0",
    "mypy>=1.11.0",
]
```

---

## Comandos de Desarrollo

```bash
# Inicializar proyecto
uv init ai-track-engineer
cd ai-track-engineer
uv sync

# Levantar infraestructura
docker compose up -d influxdb ollama

# Descargar modelo Ollama
docker compose exec ollama ollama pull mistral

# Ejecutar en modo desarrollo (con mock telemetry)
uv run python -m src.main --mock

# Ejecutar con AC real
uv run python -m src.main

# Ejecutar con voz habilitada
uv run python -m src.main --voice

# Tests
uv run pytest tests/ -v

# Lint + Type check
uv run ruff check src/
uv run mypy src/

# Entrenar modelos ML (requiere datos previos)
uv run python scripts/train_models.py

# Parsear archivos de un coche
uv run python scripts/parse_car.py --car ks_ferrari_488_gt3

# Frontend
cd frontend && npm install && npm run dev
```

---

## Notas para la Implementacion

1. **Empezar siempre por Fase 1** — No saltar fases. Cada una construye sobre la anterior.
2. **Mock primero** — Implementar `mock_telemetry.py` temprano para desarrollar sin AC.
3. **Tests en cada paso** — Cada componente debe tener tests unitarios antes de pasar al siguiente.
4. **Interfaz clara entre capas** — Usar ABCs/Protocols para que cada capa sea intercambiable.
5. **Configuracion externalizada** — Todo en `settings.yaml`, nada hardcodeado.
6. **Logging estructurado** — Usar `structlog` desde el dia 1.
7. **Voice es opt-in** — El sistema debe funcionar perfectamente sin voz (solo dashboard).
8. **ML es incremental** — Modelos empiezan vacios y mejoran con datos. Primeras sesiones usan heuristicas.
9. **Setup Lab necesita datos** — Requiere 20-30 sesiones para recomendaciones fiables. Antes: solo fisica pura.
10. **Consistencia > Velocidad** — En TODA decision del Setup Lab, priorizar lo ejecutable consistentemente.
11. **El piloto tiene la ultima palabra** — Recomendaciones son sugerencias, nunca imposiciones. El sistema aprende de aceptaciones/rechazos.
12. **Personalidad coherente** — El ingeniero mantiene personalidad consistente independientemente del backend (Copilot/Ollama/heuristica).
