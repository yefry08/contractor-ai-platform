# Contractor AI — Frontend (Fase 1)

Next.js mínimo que consume la API de `../backend`. Búsqueda de contratos,
explorador de anomalías, y vista de detalle por contrato.

## Arrancar en local

```bash
cp .env.local.example .env.local   # NEXT_PUBLIC_API_URL=http://localhost:8000
npm install
npm run dev
```

Requiere que el backend (`../backend`) esté corriendo en el puerto 8000.
