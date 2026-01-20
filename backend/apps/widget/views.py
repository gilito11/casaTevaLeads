import json
import logging
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
from core.models import Tenant
from .services import valorar_inmueble, guardar_lead_widget

logger = logging.getLogger(__name__)


def add_cors_headers(response, origin=None):
    """Agrega headers CORS para permitir embebido."""
    allowed_origins = getattr(settings, 'WIDGET_ALLOWED_ORIGINS', ['*'])

    if '*' in allowed_origins:
        response['Access-Control-Allow-Origin'] = '*'
    elif origin and origin in allowed_origins:
        response['Access-Control-Allow-Origin'] = origin
    else:
        response['Access-Control-Allow-Origin'] = '*'

    response['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response['Access-Control-Allow-Headers'] = 'Content-Type, X-Requested-With'
    response['Access-Control-Max-Age'] = '86400'
    return response


def get_tenant_by_slug(slug: str) -> Tenant:
    """Obtiene un tenant por su slug."""
    try:
        return Tenant.objects.get(slug=slug, activo=True)
    except Tenant.DoesNotExist:
        return None


@csrf_exempt
@require_http_methods(['POST', 'OPTIONS'])
def valorar_api(request):
    """
    API para valorar un inmueble.

    POST /api/widget/valorar/
    Body: {
        "tenant": "slug-inmobiliaria",
        "zona": "salou",
        "metros": 80,
        "tipo_propiedad": "piso",
        "habitaciones": 2
    }

    Response: {
        "success": true,
        "valoracion": 150000,
        "valoracion_min": 135000,
        "valoracion_max": 165000,
        "precio_m2": 1875.00,
        ...
    }
    """
    origin = request.headers.get('Origin', '')

    if request.method == 'OPTIONS':
        response = HttpResponse()
        return add_cors_headers(response, origin)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        response = JsonResponse({'success': False, 'error': 'JSON invalido'}, status=400)
        return add_cors_headers(response, origin)

    tenant_slug = data.get('tenant')
    if not tenant_slug:
        response = JsonResponse({'success': False, 'error': 'tenant es requerido'}, status=400)
        return add_cors_headers(response, origin)

    tenant = get_tenant_by_slug(tenant_slug)
    if not tenant:
        response = JsonResponse({'success': False, 'error': 'Tenant no encontrado'}, status=404)
        return add_cors_headers(response, origin)

    zona = data.get('zona', '').strip()
    metros = data.get('metros')
    tipo_propiedad = data.get('tipo_propiedad', 'piso')
    habitaciones = data.get('habitaciones')

    if not zona:
        response = JsonResponse({'success': False, 'error': 'zona es requerida'}, status=400)
        return add_cors_headers(response, origin)

    try:
        metros = float(metros) if metros else 0
    except (ValueError, TypeError):
        response = JsonResponse({'success': False, 'error': 'metros debe ser un numero'}, status=400)
        return add_cors_headers(response, origin)

    if metros <= 0:
        response = JsonResponse({'success': False, 'error': 'metros debe ser mayor que 0'}, status=400)
        return add_cors_headers(response, origin)

    try:
        habitaciones = int(habitaciones) if habitaciones else None
    except (ValueError, TypeError):
        habitaciones = None

    result = valorar_inmueble(
        zona=zona,
        metros=metros,
        tipo_propiedad=tipo_propiedad,
        habitaciones=habitaciones,
        tenant_id=tenant.tenant_id,
    )

    response = JsonResponse(result)
    return add_cors_headers(response, origin)


@csrf_exempt
@require_http_methods(['POST', 'OPTIONS'])
def lead_api(request):
    """
    API para guardar un lead captado desde el widget.

    POST /api/widget/lead/
    Body: {
        "tenant": "slug-inmobiliaria",
        "email": "user@example.com",
        "zona": "salou",
        "metros": 80,
        "tipo_propiedad": "piso",
        "habitaciones": 2,
        "direccion": "Calle Example 123",
        "telefono": "666123456",
        "valoracion": 150000
    }

    Response: {
        "success": true,
        "lead_id": "abc123..."
    }
    """
    origin = request.headers.get('Origin', '')

    if request.method == 'OPTIONS':
        response = HttpResponse()
        return add_cors_headers(response, origin)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        response = JsonResponse({'success': False, 'error': 'JSON invalido'}, status=400)
        return add_cors_headers(response, origin)

    tenant_slug = data.get('tenant')
    if not tenant_slug:
        response = JsonResponse({'success': False, 'error': 'tenant es requerido'}, status=400)
        return add_cors_headers(response, origin)

    tenant = get_tenant_by_slug(tenant_slug)
    if not tenant:
        response = JsonResponse({'success': False, 'error': 'Tenant no encontrado'}, status=404)
        return add_cors_headers(response, origin)

    email = data.get('email', '').strip()
    if not email or '@' not in email:
        response = JsonResponse({'success': False, 'error': 'email valido es requerido'}, status=400)
        return add_cors_headers(response, origin)

    zona = data.get('zona', '').strip()
    if not zona:
        response = JsonResponse({'success': False, 'error': 'zona es requerida'}, status=400)
        return add_cors_headers(response, origin)

    try:
        metros = float(data.get('metros', 0))
    except (ValueError, TypeError):
        metros = 0

    try:
        habitaciones = int(data.get('habitaciones')) if data.get('habitaciones') else None
    except (ValueError, TypeError):
        habitaciones = None

    try:
        valoracion = int(data.get('valoracion')) if data.get('valoracion') else None
    except (ValueError, TypeError):
        valoracion = None

    result = guardar_lead_widget(
        tenant_id=tenant.tenant_id,
        email=email,
        zona=zona,
        metros=metros,
        tipo_propiedad=data.get('tipo_propiedad', 'piso'),
        habitaciones=habitaciones,
        direccion=data.get('direccion', ''),
        telefono=data.get('telefono', ''),
        valoracion=valoracion,
    )

    response = JsonResponse(result)
    return add_cors_headers(response, origin)


def valorador_js(request):
    """
    Sirve el widget JavaScript embebible.

    GET /widget/valorador.js?tenant=slug&color=%23007bff
    """
    tenant_slug = request.GET.get('tenant', '')
    primary_color = request.GET.get('color', '#007bff')
    api_base = request.build_absolute_uri('/api/widget')

    # Sanitizar color
    if not primary_color.startswith('#'):
        primary_color = '#007bff'

    js_content = f'''
(function() {{
  "use strict";

  var TENANT = "{tenant_slug}";
  var PRIMARY_COLOR = "{primary_color}";
  var API_BASE = "{api_base}";

  var TIPOS_PROPIEDAD = [
    {{ value: "piso", label: "Piso" }},
    {{ value: "casa", label: "Casa" }},
    {{ value: "chalet", label: "Chalet" }},
    {{ value: "adosado", label: "Adosado" }},
    {{ value: "duplex", label: "Duplex" }},
    {{ value: "atico", label: "Atico" }},
    {{ value: "estudio", label: "Estudio" }},
    {{ value: "local", label: "Local" }},
    {{ value: "terreno", label: "Terreno" }}
  ];

  function createStyles() {{
    var style = document.createElement("style");
    style.textContent = `
      .ctv-widget {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        max-width: 400px;
        margin: 0 auto;
        padding: 24px;
        background: #fff;
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
      }}
      .ctv-widget * {{
        box-sizing: border-box;
      }}
      .ctv-widget h3 {{
        margin: 0 0 20px;
        color: #1a1a1a;
        font-size: 20px;
        font-weight: 600;
        text-align: center;
      }}
      .ctv-field {{
        margin-bottom: 16px;
      }}
      .ctv-field label {{
        display: block;
        margin-bottom: 6px;
        font-size: 14px;
        font-weight: 500;
        color: #374151;
      }}
      .ctv-field input,
      .ctv-field select {{
        width: 100%;
        padding: 10px 12px;
        font-size: 14px;
        border: 1px solid #d1d5db;
        border-radius: 8px;
        transition: border-color 0.2s, box-shadow 0.2s;
      }}
      .ctv-field input:focus,
      .ctv-field select:focus {{
        outline: none;
        border-color: ${{PRIMARY_COLOR}};
        box-shadow: 0 0 0 3px ${{PRIMARY_COLOR}}22;
      }}
      .ctv-row {{
        display: flex;
        gap: 12px;
      }}
      .ctv-row .ctv-field {{
        flex: 1;
      }}
      .ctv-btn {{
        width: 100%;
        padding: 12px;
        font-size: 16px;
        font-weight: 600;
        color: #fff;
        background: ${{PRIMARY_COLOR}};
        border: none;
        border-radius: 8px;
        cursor: pointer;
        transition: opacity 0.2s;
      }}
      .ctv-btn:hover {{
        opacity: 0.9;
      }}
      .ctv-btn:disabled {{
        opacity: 0.6;
        cursor: not-allowed;
      }}
      .ctv-result {{
        margin-top: 20px;
        padding: 20px;
        background: linear-gradient(135deg, ${{PRIMARY_COLOR}}11 0%, ${{PRIMARY_COLOR}}22 100%);
        border-radius: 12px;
        text-align: center;
      }}
      .ctv-result-label {{
        font-size: 14px;
        color: #6b7280;
        margin-bottom: 8px;
      }}
      .ctv-result-value {{
        font-size: 32px;
        font-weight: 700;
        color: ${{PRIMARY_COLOR}};
      }}
      .ctv-result-range {{
        font-size: 13px;
        color: #6b7280;
        margin-top: 8px;
      }}
      .ctv-result-info {{
        font-size: 12px;
        color: #9ca3af;
        margin-top: 12px;
      }}
      .ctv-email-section {{
        margin-top: 20px;
        padding-top: 20px;
        border-top: 1px solid #e5e7eb;
      }}
      .ctv-email-section p {{
        margin: 0 0 12px;
        font-size: 14px;
        color: #4b5563;
        text-align: center;
      }}
      .ctv-success {{
        padding: 16px;
        background: #d1fae5;
        border-radius: 8px;
        color: #065f46;
        text-align: center;
        font-size: 14px;
      }}
      .ctv-error {{
        margin-top: 12px;
        padding: 12px;
        background: #fee2e2;
        border-radius: 8px;
        color: #991b1b;
        font-size: 13px;
        text-align: center;
      }}
      .ctv-loading {{
        display: inline-block;
        width: 16px;
        height: 16px;
        border: 2px solid #fff;
        border-top-color: transparent;
        border-radius: 50%;
        animation: ctv-spin 0.8s linear infinite;
        margin-right: 8px;
        vertical-align: middle;
      }}
      @keyframes ctv-spin {{
        to {{ transform: rotate(360deg); }}
      }}
    `;
    document.head.appendChild(style);
  }}

  function formatPrice(num) {{
    return new Intl.NumberFormat("es-ES", {{
      style: "currency",
      currency: "EUR",
      maximumFractionDigits: 0
    }}).format(num);
  }}

  function createWidget(container) {{
    container.innerHTML = `
      <div class="ctv-widget">
        <h3>Valora tu inmueble</h3>
        <form id="ctv-form">
          <div class="ctv-field">
            <label>Zona / Localidad</label>
            <input type="text" id="ctv-zona" placeholder="Ej: Salou, Tarragona" required>
          </div>
          <div class="ctv-row">
            <div class="ctv-field">
              <label>Metros cuadrados</label>
              <input type="number" id="ctv-metros" placeholder="80" min="10" required>
            </div>
            <div class="ctv-field">
              <label>Habitaciones</label>
              <input type="number" id="ctv-habitaciones" placeholder="2" min="0" max="10">
            </div>
          </div>
          <div class="ctv-field">
            <label>Tipo de inmueble</label>
            <select id="ctv-tipo">
              ${{TIPOS_PROPIEDAD.map(t => '<option value="' + t.value + '">' + t.label + '</option>').join("")}}
            </select>
          </div>
          <button type="submit" class="ctv-btn" id="ctv-submit">Calcular valoracion</button>
          <div id="ctv-error" class="ctv-error" style="display:none;"></div>
        </form>
        <div id="ctv-result" style="display:none;"></div>
      </div>
    `;

    var form = document.getElementById("ctv-form");
    var submitBtn = document.getElementById("ctv-submit");
    var errorDiv = document.getElementById("ctv-error");
    var resultDiv = document.getElementById("ctv-result");
    var lastValoracion = null;

    form.addEventListener("submit", function(e) {{
      e.preventDefault();
      errorDiv.style.display = "none";
      resultDiv.style.display = "none";

      var zona = document.getElementById("ctv-zona").value.trim();
      var metros = parseFloat(document.getElementById("ctv-metros").value);
      var habitaciones = document.getElementById("ctv-habitaciones").value;
      var tipo = document.getElementById("ctv-tipo").value;

      if (!zona || !metros) {{
        errorDiv.textContent = "Por favor, completa zona y metros";
        errorDiv.style.display = "block";
        return;
      }}

      submitBtn.disabled = true;
      submitBtn.innerHTML = '<span class="ctv-loading"></span>Calculando...';

      fetch(API_BASE + "/valorar/", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{
          tenant: TENANT,
          zona: zona,
          metros: metros,
          habitaciones: habitaciones ? parseInt(habitaciones) : null,
          tipo_propiedad: tipo
        }})
      }})
      .then(function(res) {{ return res.json(); }})
      .then(function(data) {{
        submitBtn.disabled = false;
        submitBtn.textContent = "Calcular valoracion";

        if (data.success) {{
          lastValoracion = data;
          resultDiv.innerHTML = `
            <div class="ctv-result">
              <div class="ctv-result-label">Valoracion estimada</div>
              <div class="ctv-result-value">${{formatPrice(data.valoracion)}}</div>
              <div class="ctv-result-range">
                Rango: ${{formatPrice(data.valoracion_min)}} - ${{formatPrice(data.valoracion_max)}}
              </div>
              <div class="ctv-result-info">
                Basado en ${{data.num_muestras}} inmuebles similares en ${{data.zona}}
              </div>
            </div>
            <div class="ctv-email-section">
              <p>Recibe un informe detallado por email</p>
              <div class="ctv-field">
                <input type="email" id="ctv-email" placeholder="tu@email.com">
              </div>
              <button type="button" class="ctv-btn" id="ctv-send-email">Enviar informe</button>
            </div>
          `;
          resultDiv.style.display = "block";

          document.getElementById("ctv-send-email").addEventListener("click", function() {{
            sendLead(zona, metros, habitaciones, tipo, lastValoracion.valoracion);
          }});
        }} else {{
          errorDiv.textContent = data.error || "Error al calcular valoracion";
          errorDiv.style.display = "block";
        }}
      }})
      .catch(function(err) {{
        submitBtn.disabled = false;
        submitBtn.textContent = "Calcular valoracion";
        errorDiv.textContent = "Error de conexion. Intentalo de nuevo.";
        errorDiv.style.display = "block";
      }});
    }});

    function sendLead(zona, metros, habitaciones, tipo, valoracion) {{
      var email = document.getElementById("ctv-email").value.trim();
      if (!email || email.indexOf("@") === -1) {{
        alert("Por favor, introduce un email valido");
        return;
      }}

      var btn = document.getElementById("ctv-send-email");
      btn.disabled = true;
      btn.innerHTML = '<span class="ctv-loading"></span>Enviando...';

      fetch(API_BASE + "/lead/", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{
          tenant: TENANT,
          email: email,
          zona: zona,
          metros: metros,
          habitaciones: habitaciones ? parseInt(habitaciones) : null,
          tipo_propiedad: tipo,
          valoracion: valoracion
        }})
      }})
      .then(function(res) {{ return res.json(); }})
      .then(function(data) {{
        if (data.success) {{
          document.querySelector(".ctv-email-section").innerHTML = '<div class="ctv-success">Gracias. Recibiras el informe en tu email pronto.</div>';
        }} else {{
          btn.disabled = false;
          btn.textContent = "Enviar informe";
          alert(data.error || "Error al enviar");
        }}
      }})
      .catch(function() {{
        btn.disabled = false;
        btn.textContent = "Enviar informe";
        alert("Error de conexion");
      }});
    }}
  }}

  function init() {{
    createStyles();
    var containers = document.querySelectorAll("[data-ctv-widget]");
    containers.forEach(function(el) {{
      var t = el.getAttribute("data-tenant");
      var c = el.getAttribute("data-color");
      if (t) TENANT = t;
      if (c) PRIMARY_COLOR = c;
      createWidget(el);
    }});
  }}

  if (document.readyState === "loading") {{
    document.addEventListener("DOMContentLoaded", init);
  }} else {{
    init();
  }}
}})();
'''

    response = HttpResponse(js_content, content_type='application/javascript; charset=utf-8')
    response['Cache-Control'] = 'public, max-age=3600'
    return add_cors_headers(response)
