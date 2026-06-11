# Auditoría de NOVA (asíncrona, fuera del flujo)

La auditoría **no corre dentro de NOVA**. Cuando vos quieras (fin del día/semana),
abrís **Claude Code con Opus 4.8** en este repo y pegás uno de los prompts fijos de
esta carpeta. El prompt lee los registros JSONL de `logs/`, detecta patrones y
**propone** mejoras o nuevos equipos. Vos aprobás e implementás (casi siempre
editando `config/teams.yaml` / `config/tools.yaml`). Costo de API extra: **$0**
(usa tu plan). Nada se cambia sin tu aprobación.

## Cómo usar
1. Abrí Claude Code (Opus) en la raíz del repo.
2. Pegá el contenido de uno de estos archivos como prompt:
   - [`01-revision.md`](01-revision.md) — revisión general de lo que pasó.
   - [`02-nuevos-equipos.md`](02-nuevos-equipos.md) — ¿qué equipo nuevo conviene crear?
   - [`03-seguridad.md`](03-seguridad.md) — repaso de seguridad/permisos/costos.
3. Revisá las propuestas. Lo que apruebes, lo implementás editando config (sin código).

> Los registros tienen `{ts, agente, grupo, tarea, decision, modelo, resultado_breve}`
> por acción. Son la materia prima de la auditoría.
