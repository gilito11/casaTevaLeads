"""Auto-reparación con Claude Code headless en el VPS.

Cuando un paso programado falla (scheduled_scrape.py), invocamos Claude Code en
modo no-interactivo para que diagnostique y aplique un fix mínimo, lo commitee y
lo notifique por Telegram. El siguiente intento del propio paso usa ya el código
arreglado (el VPS es el runtime).

GUARDRAILS:
- Opt-in: solo actúa si AUTO_HEAL=1 en el entorno.
- Requiere que el Claude del VPS esté autenticado (`claude login` o
  ANTHROPIC_API_KEY). Sin auth, no hace nada (devuelve False).
- Un único intento de heal por paso y ejecución (lo controla quien llama).
- Claude commitea con prefijo "[auto-heal]" y hace push; Telegram avisa del
  resumen para que el cambio sea siempre visible y reversible.
- Prompt acotado: fix mínimo, sin tocar .env/credenciales, sin refactors.
"""
import os
import subprocess
import logging

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = """\
Eres el mantenedor del proyecto FincaRadar (Django + dbt + scrapers Scrapling) en {root}.
Un paso programado ha FALLADO y debes intentar arreglarlo de forma autónoma y SEGURA.

STEP QUE FALLÓ: {step}

ERROR (cola del log):
--------------------
{error}
--------------------

INSTRUCCIONES:
1. Diagnostica la causa raíz leyendo SOLO los archivos implicados (usa Grep/Read).
2. Aplica el fix MÍNIMO y reversible. NO refactorices. NUNCA toques .env, secretos
   ni credenciales. Si el error es de datos externos (portal caído, proxy, captcha),
   NO cambies código: explícalo y termina sin commitear.
3. Si tocas un modelo dbt, valídalo con:
   venv\\Scripts\\dbt.exe compile --select <modelo> --project-dir dbt_project --profiles-dir dbt_project
4. Si y solo si has aplicado un fix de código del que estás razonablemente seguro:
   - git add <archivos>
   - git commit -m "[auto-heal] <descripción corta del fix>"
   - git push origin master
5. Si NO estás seguro de la causa, o el fix es arriesgado, o es un problema de
   infraestructura/datos: NO cambies nada y explica por qué.

Termina SIEMPRE con un bloque final de 2-4 líneas: "RESUMEN:" y qué hiciste (o por qué no).
"""


def is_enabled() -> bool:
    return os.environ.get("AUTO_HEAL", "").strip().lower() in ("1", "true", "yes", "on")


def heal(step_desc: str, error_log: str, project_root: str, timeout: int = 1200):
    """Invoca Claude headless. Devuelve (intentado: bool, resumen: str)."""
    if not is_enabled():
        return False, "AUTO_HEAL desactivado"

    claude_bin = os.environ.get("CLAUDE_BIN", "claude")
    prompt = _PROMPT_TEMPLATE.format(
        root=project_root, step=step_desc, error=(error_log or "")[-3500:]
    )
    cmd = [
        claude_bin, "-p",
        "--permission-mode", "acceptEdits",
        "--allowedTools", "Read,Edit,Grep,Glob,Bash",
        "--max-turns", "30",
    ]
    try:
        result = subprocess.run(
            cmd, input=prompt, cwd=project_root,
            capture_output=True, text=True, timeout=timeout,
            env={**os.environ},
        )
    except subprocess.TimeoutExpired:
        return True, f"Claude auto-heal TIMEOUT ({timeout}s) en: {step_desc}"
    except FileNotFoundError:
        return False, "Claude CLI no encontrado (revisa CLAUDE_BIN/PATH)"

    out = (result.stdout or "").strip()
    # Quedarnos con el RESUMEN final si existe
    if "RESUMEN:" in out:
        summary = "RESUMEN:" + out.split("RESUMEN:", 1)[1]
    else:
        summary = out[-1200:] or (result.stderr or "")[-600:]
    if result.returncode != 0 and not summary:
        summary = f"Claude rc={result.returncode}: {(result.stderr or '')[-400:]}"
    return True, summary.strip()
