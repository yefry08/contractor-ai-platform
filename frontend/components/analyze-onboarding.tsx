"use client";

import { useState } from "react";
import { useLanguage } from "@/lib/language-context";

export function AnalyzeOnboarding() {
  const { t } = useLanguage();
  const [expanded, setExpanded] = useState(false);

  const steps = [
    { icon: "📄", key: "s1", tips: 3 },
    { icon: "🔍", key: "s2", tips: 3 },
    { icon: "📊", key: "s3", tips: 3 },
    { icon: "🤖", key: "s4", tips: 3 },
  ];
  const questions = ["q1", "q2", "q3"];
  const facts = ["f1", "f2", "f3", "f4", "f5"];

  return (
    <div className="analyze-onboarding" style={{ marginBottom: 30 }}>
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
        className="onboarding-toggle"
      >
        <span style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <span style={{ fontSize: "20px" }}>💡</span>
          <span>
            <strong>{t("onboarding.toggleTitle")}</strong>
            <span className="onboarding-toggle-sub">{t("onboarding.toggleSub")}</span>
          </span>
        </span>
        <span style={{ fontSize: "20px" }}>{expanded ? "▼" : "▶"}</span>
      </button>

      {expanded && (
        <div style={{ marginTop: 20 }}>
          <div style={{ marginBottom: 30 }}>
            <h3 style={{ marginTop: 0, marginBottom: 16 }}>📋 {t("onboarding.stepsTitle")}</h3>
            <div className="onboarding-grid">
              {steps.map((step) => (
                <div key={step.key} className="onboarding-card">
                  <div style={{ fontSize: "24px", marginBottom: 8 }}>{step.icon}</div>
                  <h4 style={{ margin: "0 0 8px 0", color: "var(--accent)" }}>
                    {t(`onboarding.${step.key}Title`)}
                  </h4>
                  <p style={{ margin: "0 0 12px 0", fontSize: "0.95em" }}>
                    {t(`onboarding.${step.key}Desc`)}
                  </p>
                  <ul style={{ margin: 0, paddingLeft: 20, fontSize: "0.9em" }}>
                    {Array.from({ length: step.tips }, (_, j) => (
                      <li key={j} style={{ marginBottom: 6 }}>
                        {t(`onboarding.${step.key}Tip${j + 1}`)}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </div>

          <div style={{ marginBottom: 20 }}>
            <h3 style={{ marginBottom: 16 }}>❓ {t("onboarding.interpretTitle")}</h3>
            <div style={{ display: "grid", gap: 16 }}>
              {questions.map((q) => (
                <div key={q} className="onboarding-question">
                  <h4 style={{ margin: "0 0 8px 0" }}>{t(`onboarding.${q}Title`)}</h4>
                  <p style={{ margin: "0 0 8px 0", fontSize: "0.95em" }}>{t(`onboarding.${q}Desc`)}</p>
                  <div className="onboarding-example">
                    <strong>{t("onboarding.example")}:</strong> {t(`onboarding.${q}Example`)}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="onboarding-facts">
            <h3 style={{ margin: "0 0 12px 0" }}>✅ {t("onboarding.keyFactsTitle")}</h3>
            <ul style={{ margin: 0, paddingLeft: 20, fontSize: "0.95em" }}>
              {facts.map((f) => (
                <li key={f}>
                  <strong>{t(`onboarding.${f}Label`)}:</strong> {t(`onboarding.${f}Text`)}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
