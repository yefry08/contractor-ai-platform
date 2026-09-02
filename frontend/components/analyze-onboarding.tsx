"use client";

import { useState } from "react";

export function AnalyzeOnboarding() {
  const [expanded, setExpanded] = useState(false);

  const steps = [
    {
      icon: "📄",
      title: "Paso 1: Cargar documento",
      description: "Subí un PDF (nativo o escaneado) o pegá un enlace a la publicación oficial del contrato.",
      tips: [
        "PDFs escaneados se procesan con OCR automático",
        "También aceptamos enlaces públicos a documentos",
        "Si hay error de OCR, los datos sugeridos pueden no ser exactos",
      ],
    },
    {
      icon: "🔍",
      title: "Paso 2: Extraer datos",
      description: "El sistema lee el documento y sugiere: título, monto, categoría y organismo comprador.",
      tips: [
        "Revisá que el monto esté correctamente detectado",
        "Si el OCR no fue perfecto, corregí manualmente",
        "La moneda se auto-detecta según el país",
      ],
    },
    {
      icon: "📊",
      title: "Paso 3: Comparar",
      description: "Se compara el contrato contra 100+ similares del mismo país/categoría usando estadística pura (sin IA).",
      tips: [
        "Usa mediana + MAD (desviación absoluta media) — robusto contra outliers",
        "Muestra el rango típico de precios para contratos similares",
        "El veredicto es 100% basado en datos, completamente transparente",
      ],
    },
    {
      icon: "🤖",
      title: "Paso 4: Resumen IA (opcional)",
      description: "Genera un resumen en lenguaje natural del contrato usando IA.",
      tips: [
        "Solo disponible con API key configurada (BazaarLink)",
        "No es parte del veredicto — es un resumen de contexto",
        "Útil para entender rápidamente qué es el contrato",
      ],
    },
  ];

  const examples = [
    {
      title: "¿Qué es un contrato con alta desviación?",
      description: "Un contrato cuyo monto es 2x+ mayor que similares en el mismo país/categoría/método de compra.",
      example: "Reparación de ruta: debería costar $50k, pero pagaron $150k",
    },
    {
      title: "¿Qué significa 'Revisar'?",
      description: "El monto está ligeramente elevado pero no es anómalo. Podría haber variables no capturadas (urgencia, especificidad, etc.).",
      example: "Un contrato 15-25% por encima del rango típico",
    },
    {
      title: "¿Cómo leo el rango de referencia?",
      description: 'El rango "típico" muestra el 50% central de contratos similares. Fuera de ese rango = inusual.',
      example: "Si típico es $50k–$100k y tu contrato es $200k → investigar",
    },
  ];

  return (
    <div className="analyze-onboarding" style={{ marginBottom: 30 }}>
      <div
        onClick={() => setExpanded(!expanded)}
        style={{
          cursor: "pointer",
          padding: "12px 16px",
          backgroundColor: "rgba(33, 150, 243, 0.08)",
          border: "1px solid rgba(33, 150, 243, 0.3)",
          borderRadius: "6px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <span style={{ fontSize: "20px" }}>💡</span>
          <div>
            <strong>¿Cómo analizar un contrato?</strong>
            <p style={{ margin: 0, fontSize: "0.9em", color: "var(--muted)" }}>
              Guía paso a paso + ejemplos de interpretación
            </p>
          </div>
        </div>
        <span style={{ fontSize: "20px" }}>{expanded ? "▼" : "▶"}</span>
      </div>

      {expanded && (
        <div style={{ marginTop: 20 }}>
          {/* Steps */}
          <div style={{ marginBottom: 30 }}>
            <h3 style={{ marginTop: 0, marginBottom: 16 }}>📋 Pasos del análisis</h3>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              {steps.map((step, i) => (
                <div
                  key={i}
                  style={{
                    padding: 16,
                    border: "1px solid var(--border)",
                    borderRadius: "6px",
                    backgroundColor: "var(--panel)",
                  }}
                >
                  <div style={{ fontSize: "24px", marginBottom: 8 }}>{step.icon}</div>
                  <h4 style={{ margin: "0 0 8px 0", color: "var(--accent)" }}>{step.title}</h4>
                  <p style={{ margin: "0 0 12px 0", fontSize: "0.95em" }}>{step.description}</p>
                  <ul style={{ margin: 0, paddingLeft: 20, fontSize: "0.9em" }}>
                    {step.tips.map((tip, j) => (
                      <li key={j} style={{ marginBottom: 6 }}>
                        {tip}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </div>

          {/* Examples */}
          <div style={{ marginBottom: 20 }}>
            <h3 style={{ marginBottom: 16 }}>❓ Cómo interpretar resultados</h3>
            <div style={{ display: "grid", gap: 16 }}>
              {examples.map((ex, i) => (
                <div
                  key={i}
                  style={{
                    padding: 16,
                    backgroundColor: "rgba(255, 193, 7, 0.05)",
                    border: "1px solid rgba(255, 193, 7, 0.3)",
                    borderRadius: "6px",
                  }}
                >
                  <h4 style={{ margin: "0 0 8px 0" }}>{ex.title}</h4>
                  <p style={{ margin: "0 0 8px 0", fontSize: "0.95em" }}>{ex.description}</p>
                  <div style={{ padding: 8, backgroundColor: "rgba(0,0,0,0.03)", borderRadius: 4, fontSize: "0.9em" }}>
                    <strong>Ejemplo:</strong> {ex.example}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Key facts */}
          <div
            style={{
              padding: 16,
              backgroundColor: "rgba(76, 175, 80, 0.05)",
              border: "1px solid rgba(76, 175, 80, 0.3)",
              borderRadius: "6px",
            }}
          >
            <h3 style={{ margin: "0 0 12px 0" }}>✅ Cosas importantes</h3>
            <ul style={{ margin: 0, paddingLeft: 20, fontSize: "0.95em" }}>
              <li>
                <strong>100% estadístico:</strong> Sin IA ni criterio arbitrario en el veredicto
              </li>
              <li>
                <strong>Robusto:</strong> Usa mediana + MAD, no se distorsiona por valores extremos
              </li>
              <li>
                <strong>Transparente:</strong> Ves el rango de referencia, el z-score, todo abierto
              </li>
              <li>
                <strong>Contextual:</strong> Compara por país, categoría, método de compra y comprador
              </li>
              <li>
                <strong>No es conclusión:</strong> Es una SEÑAL a investigar, no un veredicto legal
              </li>
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
