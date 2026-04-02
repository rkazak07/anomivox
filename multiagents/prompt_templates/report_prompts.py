
ANOMALY_DESC_PROMPT='''
Please describe the following anomaly event in natural language:
{anomaly_str}

Note do not miss any important information in each line of the event. And the description templates should be like:

1. "During the inspection, it was found that from xx to xx time, the database's CPU usage was relatively high, approximately 80% to 90%. It is a *critical problem*, please solve it as soon as possible."

2. "During the inspection, it was found that from xx to xx time, the database's CPU usage was relatively high, approximately 80% to 90%. It is just a *warning*, please take time to solve it carefully."
'''

ANOMALY_DESC_PROMPT_zh = '''
{anomaly_str}

'''

ANOMALY_DESC_PROMPT_tr = '''
Aşağıdaki anomali olayını Türkçe olarak doğal dilde açıkla:
{anomaly_str}

Not: Olayın her satırındaki bilgileri eksik bırakma. Açıklama şablonu şöyle olmalı:
"Kontrolde, xx - xx saatleri arasında veritabanı CPU kullanımının yaklaşık %80-90 gibi yüksek olduğu tespit edilmiştir. Bu *kritik bir sorun*, lütfen bir an önce çözün."
Yanıtını Türkçe yaz.
'''

ANOMALY_TITLE_PROMPT='''
Please give a title for the following anomaly event within 15 words:
{anomaly_str}

Note the title template is like:
Analysis Report of High CPU Usage
'''

ANOMALY_TITLE_PROMPT_zh = '''
{anomaly_str}

'''

ANOMALY_TITLE_PROMPT_tr = '''
Aşağıdaki anomali olayı için 15 kelimeyi geçmeyecek şekilde Türkçe bir başlık oluştur:
{anomaly_str}

Başlık şablonu örneği:
Yüksek CPU Kullanımı Analiz Raporu
Yanıtını Türkçe yaz.
'''

