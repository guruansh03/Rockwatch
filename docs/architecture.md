# Architecture

```mermaid
flowchart LR
  subgraph Replay
    ENG[Replay engine<br/>sim.clock ticks] -->|after day closes| TRUTH[(truth.events)]
  end
  ENG --> SR1[RainSensor g0] & SR2[RainSensor g1] & ST[ThermalSensor] & SS[SeismicSensor]
  SR1 & SR2 -->|sensor.rain| Q[QualityAgent]
  ST -->|sensor.thermal| Q
  SR1 & SR2 & ST --> ER[Evidence Rain]
  ST --> ET[Evidence Thermal]
  SS -->|sensor.seismic| ES[Evidence Seismic]
  ENG --> EP[Evidence Susceptibility]
  ER -->|evidence.rain| CX[ContextAgent]
  ER & ET & ES & EP & CX -->|evidence.*| F[FusionAgent<br/>logit = b0 + Σ w_q·c]
  Q -->|quality.flags| F
  F -->|risk.fused| V[LLM-Verifier<br/>tools + guardrails]
  V -->|risk.verified| A[AlertAgent<br/>hysteresis · ack · re-notify]
  A -->|alerts.active| C[LLM-AlertComposer]
  A --> DASH[Streamlit dashboard]
  C --> DASH
  DASH -->|alerts.ack / agents.control| A
  HB[all agents] -->|agents.heartbeat| SUP[Supervisor] -->|stale / restart| F
  A --> EV[EvaluatorAgent]
  TRUTH --> EV
  TRUTH -. overlay .-> DASH
  AN[LLM-Analyst] -->|read-only tools| DASH
```

- **Bus**: append-only log with per-consumer offsets — SQLite WAL (demo, multi-process), in-memory (tests/batch). Envelope:
  `{msg_id, topic, agent_id, zone_id, sim_date, wall_ts, kind, payload, confidence, quality, evidence_ids}`.
- **Agents**: one OS process each (16 with the composer), heartbeat every 2 s, decision logic in pure step functions shared with batch evaluation (parity-tested).
- **Truth isolation**: only the evaluator and the dashboard overlay may read `truth.events` (bus access control + static test).
- **Quality**: modality weight 1.0 ok / 0.5 degraded / 0 missing; supervisor marks stale agents; deadlines close late days.
- **LLM**: verifier never raises a level; all rules enforced in code (`docs/llm_guardrails.md`).
