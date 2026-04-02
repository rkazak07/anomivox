
DIAGNOSIS_SUMMARY_PROMPT = '''
Please provide a searchable summary of the input diagnosis procedures or recommended solutions without losing important information. The input is as follows:
{diagnosis_messages}

=============
Note 
1. you are an expert and do not miss any important information!!!
2. response with a list of key points of the input diagnosis procedures or recommended solutions (e.g. "1. ...<br>2. ...<br>3. ..."). Do not add any additional content!!!
3. The key points should be strictly separated by <br> ("1. ...<br>2. ...<br>3. ...")!!!! Do not use markdown format and # headings!!!
4. Do not mention anything about what are the charts like!! Ignore charts!!!
5. Do not say anything like "As an AI"!!
'''

DIAGNOSIS_SUMMARY_PROMPT_zh = '''
{diagnosis_messages}

2. List key points one by one (e.g. 1. ...<br>2. ...<br>3. ...). Do not add any extra content!
3. Key points must be separated by <br> (e.g. 1. ...<br>2. ...<br>3. ...). Do not use markdown format.
'''

DIAGNOSIS_SUMMARY_PROMPT_tr = '''
Aşağıdaki tanı prosedürleri veya önerilen çözümlerin önemli bilgileri kaybetmeden aranabilir bir özetini Türkçe olarak ver:
{diagnosis_messages}

=============
Not
1. Uzman olarak önemli bilgileri atlama!
2. Giriş tanı prosedürleri veya önerilen çözümlerin temel noktalarını liste hâlinde yanıtla (örn. "1. ...<br>2. ...<br>3. ..."). Ek içerik ekleme!
3. Temel noktalar <br> ile kesinlikle ayrılmalı ("1. ...<br>2. ...<br>3. ...")! Markdown formatı ve # başlıkları kullanma!
4. Grafiklere ilişkin hiçbir şey söyleme! Grafikleri yoksay!
5. "Yapay Zeka olarak" gibi ifadeler kullanma!
6. Yanıtını Türkçe yaz.
'''