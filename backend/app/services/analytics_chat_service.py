from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

import ollama
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.attribute import AtributoMencionado
from app.models.establishment_sentiment import SentimientoEstablecimiento
from app.models.sentiment import SentimientoPlatillo
from app.schemas.analytics import AnalyticsChatPlan
from app.services.ranking_service import wilson_score_lower_bound


class AnalyticsChatError(Exception):
    """La pregunta no pudo interpretarse mediante Ollama."""


class AnalyticsChatService:
    def __init__(self):
        self.client = ollama.Client(host=settings.OLLAMA_BASE_URL)
        self.model_name = settings.OLLAMA_MODEL

    def _interpret(self, question: str) -> AnalyticsChatPlan:
        prompt = f"""Convierte la pregunta en una consulta analítica para un CRM de restaurante.
Devuelve solo el JSON del esquema indicado.

Métricas: menciones, positivas, negativas, neutrales, wilson_score.
Agrupaciones: platillo, atributo, establecimiento.
Usa wilson_score únicamente con agrupacion platillo. El periodo es de 1 a 90 días; si no se indica, usa 7.
No inventes métricas ni filtros. "Mejor platillo" equivale a wilson_score por platillo.

Pregunta: {question}"""
        try:
            result = self.client.chat(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                format=AnalyticsChatPlan.model_json_schema(),
                options={"temperature": 0.0, "seed": 42},
            )
            plan = AnalyticsChatPlan.model_validate_json(result.message.content)
        except Exception as exc:
            raise AnalyticsChatError("No se pudo interpretar la pregunta con Ollama.") from exc
        if plan.metrica.value == "wilson_score" and plan.agrupacion.value != "platillo":
            raise AnalyticsChatError("Wilson Score solo se puede consultar por platillo.")
        return plan

    @staticmethod
    def _label(metric: str) -> str:
        return {
            "menciones": "menciones",
            "positivas": "menciones positivas",
            "negativas": "menciones negativas",
            "neutrales": "menciones neutrales",
            "wilson_score": "Wilson Score",
        }[metric]

    @staticmethod
    def _polarity_key(polarity: str) -> str:
        return {"positivo": "positivas", "negativo": "negativas", "neutral": "neutrales"}[polarity]

    def _dish_data(self, db: Session, plan: AnalyticsChatPlan, cutoff: datetime) -> list[dict[str, Any]]:
        sentiments = db.query(SentimientoPlatillo).filter(
            SentimientoPlatillo.platillo_id.isnot(None),
            SentimientoPlatillo.platillo_nombre_referenciado != "Sin Clasificar",
            SentimientoPlatillo.created_at >= cutoff,
        ).all()
        grouped = defaultdict(lambda: {"nombre": "", "positivas": 0, "negativas": 0, "neutrales": 0})
        for sentiment in sentiments:
            item = grouped[sentiment.platillo_id]
            item["nombre"] = sentiment.platillo.nombre if sentiment.platillo else sentiment.platillo_nombre_referenciado
            item[self._polarity_key(sentiment.polaridad)] += 1
        result = []
        for item in grouped.values():
            total = sum(item[key] for key in ("positivas", "negativas", "neutrales"))
            value = (
                wilson_score_lower_bound(item["positivas"], total)
                if plan.metrica.value == "wilson_score"
                else total if plan.metrica.value == "menciones"
                else item[plan.metrica.value]
            )
            result.append({"etiqueta": item["nombre"], "valor": value})
        return result

    def _category_data(self, db: Session, plan: AnalyticsChatPlan, cutoff: datetime) -> list[dict[str, Any]]:
        model = AtributoMencionado if plan.agrupacion.value == "atributo" else SentimientoEstablecimiento
        query = db.query(model)
        if model is AtributoMencionado:
            query = query.join(SentimientoPlatillo).filter(SentimientoPlatillo.created_at >= cutoff)
        else:
            query = query.filter(SentimientoEstablecimiento.created_at >= cutoff)
        grouped = defaultdict(lambda: {"positivas": 0, "negativas": 0, "neutrales": 0})
        for item in query.all():
            label = item.categoria_atributo if model is AtributoMencionado else item.categoria
            grouped[label][self._polarity_key(item.polaridad)] += 1
        return [
            {"etiqueta": label, "valor": sum(values.values()) if plan.metrica.value == "menciones" else values[plan.metrica.value]}
            for label, values in grouped.items()
        ]

    def ask(self, db: Session, question: str) -> dict[str, Any]:
        plan = self._interpret(question)
        cutoff = datetime.now(timezone.utc) - timedelta(days=plan.periodo_dias)
        data = self._dish_data(db, plan, cutoff) if plan.agrupacion.value == "platillo" else self._category_data(db, plan, cutoff)
        data.sort(key=lambda item: item["valor"], reverse=True)
        data = data[:10]
        metric_label = self._label(plan.metrica.value)
        group_label = {"platillo": "platillo", "atributo": "atributo", "establecimiento": "aspecto del establecimiento"}[plan.agrupacion.value]
        title = f"{metric_label.capitalize()} por {group_label} (últimos {plan.periodo_dias} días)"
        response = "No hay datos para el período solicitado." if not data else f"Se muestran los {len(data)} resultados principales por {metric_label}."
        return {
            "respuesta": response,
            "consulta_interpretada": plan.model_dump(mode="json"),
            "grafica": {
                "tipo": "bar",
                "titulo": title,
                "eje_x": "etiqueta",
                "eje_y": "valor",
                "datos": data,
            },
        }


analytics_chat_service = AnalyticsChatService()
