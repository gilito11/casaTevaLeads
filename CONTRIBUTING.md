# 🤝 Contribuir a Casa Teva Lead System

¡Gracias por tu interés en contribuir! Este documento te guía sobre cómo hacerlo.

## 📋 Proceso de Contribución

### 1. Reportar Bugs
- Usa la [plantilla de bug report](.github/ISSUE_TEMPLATE/bug_report.md)
- Incluye pasos para reproducir el problema
- Indica el portal afectado si aplica

### 2. Proponer Features
- Usa la [plantilla de feature request](.github/ISSUE_TEMPLATE/feature_request.md)
- Describe el caso de uso claramente

### 3. Pull Requests

```bash
# 1. Fork y clona
git clone https://github.com/tu-usuario/casaTevaLeads.git

# 2. Crea una rama
git checkout -b feat/mi-feature   # Para features
git checkout -b fix/mi-fix        # Para fixes

# 3. Haz tus cambios y commitea
git commit -m "feat: descripción clara del cambio"

# 4. Push y crea PR
git push origin feat/mi-feature
```

## 🎯 Convenciones

### Commits
Usamos [Conventional Commits](https://www.conventionalcommits.org/):
- `feat:` nueva funcionalidad
- `fix:` corrección de bug
- `docs:` cambios en documentación
- `refactor:` refactorización de código
- `test:` añadir o modificar tests

### Código
- Python: seguir PEP 8
- Django: seguir las convenciones de Django
- Scrapers: documentar cambios en selectores HTML

## 🧪 Testing

```bash
# Backend Django
cd backend && python manage.py test

# dbt
cd dbt_project && dbt test
```

## 📁 Estructura de PRs

Tu PR debe:
- [ ] Tener un título descriptivo
- [ ] Incluir descripción del cambio
- [ ] Pasar los tests existentes
- [ ] No romper la funcionalidad actual

## ❓ Dudas

Abre un issue con la etiqueta `question`.

---

¡Gracias por contribuir! 🙌
