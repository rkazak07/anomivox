"""
Prediction API
═══════════════
Prometheus metriklerinden kısa vadeli (1-4 saat) tahmin endpoint'leri.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Header
from pydantic import BaseModel
from server.utils import BaseResponse
from server.auth.auth_api import _get_current_user

logger = logging.getLogger("server.prediction_api")

STEP_MINUTES = 5  # Prometheus step = 5 dakika


class ForecastBody(BaseModel):
    metric_name: str
    horizon_hours: int = 2       # 1-4 saat
    lookback_hours: int = 24


async def api_get_supported_metrics(Authorization: str = Header(None)):
    from server.prediction.prometheus_fetcher import get_supported_metrics
    return BaseResponse(data=get_supported_metrics())


async def api_get_forecast(body: ForecastBody, Authorization: str = Header(None)):
    """Belirtilen metrik için tahmin hesapla."""
    user = _get_current_user(Authorization)
    if not user:
        return BaseResponse(code=401, msg='Unauthorized')

    horizon_hours = max(1, min(4, body.horizon_hours))
    steps = int((horizon_hours * 60) / STEP_MINUTES)  # kaç tahmin adımı

    try:
        from server.prediction.prometheus_fetcher import fetch_metric, METRIC_THRESHOLDS
        data_points = await fetch_metric(body.metric_name, lookback_hours=body.lookback_hours)

        if len(data_points) < 10:
            return BaseResponse(code=200, data={
                'metric_name': body.metric_name,
                'has_data': False,
                'message': 'Tahmin için yeterli veri yok.',
            })

        values = [p['value'] for p in data_points]
        current_value = values[-1]
        threshold = METRIC_THRESHOLDS.get(body.metric_name)

        from server.prediction.arima_predictor import forecast, will_breach_threshold
        forecast_values = forecast(values, steps=steps)

        breach_step = will_breach_threshold(forecast_values, threshold) if threshold else None
        will_breach = breach_step is not None
        breach_at_minutes = breach_step * STEP_MINUTES if will_breach else None

        # Tahmin zaman damgaları oluştur
        now = datetime.utcnow()
        forecast_series = []
        for i, v in enumerate(forecast_values):
            ts = (now + timedelta(minutes=(i + 1) * STEP_MINUTES)).isoformat() + 'Z'
            forecast_series.append({'timestamp': ts, 'value': round(v, 2)})

        result = {
            'metric_name': body.metric_name,
            'has_data': True,
            'current_value': round(current_value, 2),
            'threshold': threshold,
            'will_breach': will_breach,
            'breach_at_minutes': breach_at_minutes,
            'horizon_hours': horizon_hours,
            'history': [
                {'timestamp': datetime.utcfromtimestamp(p['timestamp']).isoformat() + 'Z',
                 'value': round(p['value'], 2)}
                for p in data_points[-60:]  # Son 5 saat göster
            ],
            'forecast': forecast_series,
        }
        return BaseResponse(data=result)

    except Exception as e:
        logger.error(f"Forecast hatası ({body.metric_name}): {e}", exc_info=True)
        return BaseResponse(code=500, msg=f'Tahmin hatası: {str(e)[:200]}')


async def api_run_alert_check(Authorization: str = Header(None)):
    """Tüm metrikler için tahmin kontrol et, eşik aşımı öngörülenleri alert et."""
    user = _get_current_user(Authorization)
    if not user or not user.get('is_admin'):
        return BaseResponse(code=401, msg='Unauthorized')

    from server.prediction.prometheus_fetcher import get_supported_metrics, fetch_metric, METRIC_THRESHOLDS
    from server.prediction.arima_predictor import forecast, will_breach_threshold
    from server.prediction.alert_dispatcher import send_predictive_alert

    alerts_sent = []
    for metric_info in get_supported_metrics():
        metric = metric_info['name']
        threshold = metric_info.get('threshold')
        if not threshold:
            continue
        try:
            data_points = await fetch_metric(metric, lookback_hours=6)
            if len(data_points) < 10:
                continue
            values = [p['value'] for p in data_points]
            current_value = values[-1]
            forecast_values = forecast(values, steps=24)  # 2 saat ilerisi
            breach_step = will_breach_threshold(forecast_values, threshold)
            if breach_step is not None:
                breach_at_minutes = breach_step * STEP_MINUTES
                await send_predictive_alert(
                    metric=metric,
                    current_value=current_value,
                    forecast_value=forecast_values[breach_step],
                    breach_at_minutes=breach_at_minutes,
                    threshold=threshold,
                )
                alerts_sent.append({'metric': metric, 'breach_at_minutes': breach_at_minutes})
        except Exception as e:
            logger.warning(f"Alert kontrol hatası ({metric}): {e}")

    return BaseResponse(data={'alerts_sent': alerts_sent, 'checked': len(get_supported_metrics())})
