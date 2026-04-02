"""
ARIMA Predictor
════════════════
statsmodels ARIMA tabanlı zaman serisi tahmini.
Statsmodels yoksa lineer trend fallback kullanılır.
"""

import logging
from typing import List, Optional

logger = logging.getLogger("server.prediction.arima_predictor")


def forecast(values: List[float], steps: int = 12) -> List[float]:
    """
    Verilen değer listesinden `steps` adım ilerisi için tahmin yap.
    ARIMA başarısız olursa lineer trend kullanılır.

    Args:
        values: Geçmiş değerler (en az 10 eleman)
        steps: Tahmin adım sayısı (5 dakikalık step'lerle)

    Returns:
        Tahmin edilen değerler listesi
    """
    if len(values) < 10:
        return []

    try:
        return _arima_forecast(values, steps)
    except Exception as e:
        logger.warning(f"ARIMA başarısız, lineer trend kullanılıyor: {e}")
        return _linear_trend_forecast(values, steps)


def _arima_forecast(values: List[float], steps: int) -> List[float]:
    from statsmodels.tsa.arima.model import ARIMA
    import warnings
    warnings.filterwarnings('ignore')

    # ARIMA(1,1,1) — basit ama güçlü
    model = ARIMA(values, order=(1, 1, 1))
    fit = model.fit()
    forecast_result = fit.forecast(steps=steps)
    return [max(0.0, float(v)) for v in forecast_result]


def _linear_trend_forecast(values: List[float], steps: int) -> List[float]:
    """Son N değere lineer regresyon uygula."""
    n = min(len(values), 30)
    recent = values[-n:]
    x = list(range(n))

    # Basit lineer regresyon
    x_mean = sum(x) / n
    y_mean = sum(recent) / n
    numerator = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, recent))
    denominator = sum((xi - x_mean) ** 2 for xi in x)
    slope = numerator / denominator if denominator != 0 else 0
    intercept = y_mean - slope * x_mean

    return [max(0.0, slope * (n + i) + intercept) for i in range(steps)]


def will_breach_threshold(forecast_values: List[float], threshold: float) -> Optional[int]:
    """
    Eşik değerini hangi adımda aşıyorsa o adımı döndür.
    Aşmıyorsa None döner.
    """
    for i, v in enumerate(forecast_values):
        if v >= threshold:
            return i
    return None
