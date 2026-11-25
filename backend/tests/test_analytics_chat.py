from types import SimpleNamespace
from unittest.mock import MagicMock

from app.core.database import SessionLocal
from app.services.analytics_chat_service import analytics_chat_service


def test_analytics_chat_returns_chart_json(monkeypatch):
    client = MagicMock()
    client.chat.return_value = SimpleNamespace(
        message=SimpleNamespace(content='{"metrica":"negativas","agrupacion":"platillo","periodo_dias":7}')
    )
    monkeypatch.setattr(analytics_chat_service, "client", client)
    db = SessionLocal()
    try:
        response = analytics_chat_service.ask(db, "¿Qué platillos tienen más quejas?")
    finally:
        db.close()

    assert response["consulta_interpretada"] == {"metrica": "negativas", "agrupacion": "platillo", "periodo_dias": 7}
    assert response["grafica"]["tipo"] == "bar"
    assert isinstance(response["grafica"]["datos"], list)
