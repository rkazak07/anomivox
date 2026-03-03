
PROMPT_TEMPLATES = {
    "llm_chat": {
        # --- English ---
        "default":
            '{{ input }}',

        "with_history":
            'The following is a friendly conversation between a human and an AI. '
            'The AI is talkative and provides lots of specific details from its context. '
            'If the AI does not know the answer to a question, it truthfully says it does not know.\n\n'
            'Current conversation:\n'
            '{history}\n'
            'Human: {input}\n'
            'AI:',

        "py":
            '{{ input }}',

        # --- Turkish ---
        "tr":
            '{{ input }}',

        "with_history_tr":
            'Aşağıdaki, bir insan ile bir yapay zeka arasındaki samimi bir konuşmadır. '
            'Yapay zeka konuşkan olup bağlamından çok sayıda spesifik ayrıntı sağlar. '
            'Yapay zeka bir sorunun cevabını bilmiyorsa, bunu dürüstçe söyler.\n\n'
            'Mevcut konuşma:\n'
            '{history}\n'
            'İnsan: {input}\n'
            'YZ:',
    },


    "knowledge_base_chat": {
        # --- English ---
        "default":
            'Use the following context from the knowledge base to answer the question. '
            'If the answer is found in the context, provide a detailed response based on it. '
            'If the context does not contain relevant information, clearly state that.\n\n'
            '<context>{{ context }}</context>\n\n'
            'Question: {{ question }}\n'
            'Answer:',

        "text":
            'Use the following context from the knowledge base to answer the question. '
            'If the answer is found in the context, provide a detailed response based on it. '
            'If the context does not contain relevant information, clearly state that.\n\n'
            '<context>{{ context }}</context>\n\n'
            'Question: {{ question }}\n'
            'Answer:',

        "empty":
            '{{ question }}\n\n',

        # --- Turkish ---
        "tr":
            'Aşağıdaki bilgi tabanı bağlamını kullanarak soruyu cevapla. '
            'Cevap bağlamda bulunuyorsa, bağlama dayalı ayrıntılı bir yanıt ver. '
            'Bağlamda ilgili bilgi yoksa bunu açıkça belirt.\n\n'
            '<bağlam>{{ context }}</bağlam>\n\n'
            'Soru: {{ question }}\n'
            'Cevap:',

        "empty_tr":
            '{{ question }}\n\n',
    },


    "search_engine_chat": {
        # --- English ---
        "default":
            '<known-information>{{ context }}</known-information>\n'
            '<question>{{ question }}</question>\n',

        "search":
            '<known-information>{{ context }}</known-information>\n'
            '<question>{{ question }}</question>\n',

        # --- Turkish ---
        "tr":
            '<bilinen-bilgi>{{ context }}</bilinen-bilgi>\n'
            '<soru>{{ question }}</soru>\n',
    },


    "agent_chat": {
        # --- English ---
        "default":
            'Answer the following questions as best you can. If it is in order, you can use some tools appropriately. '
            'You have access to the following tools:\n\n'
            '{tools}\n\n'
            'Use the following format:\n'
            'Question: the input question you must answer\n'
            'Thought: you should always think about what to do and what tools to use.\n'
            'Action: the action to take, should be one of [{tool_names}]\n'
            'Action Input: the input to the action\n'
            'Observation: the result of the action\n'
            '... (this Thought/Action/Action Input/Observation can be repeated zero or more times)\n'
            'Thought: I now know the final answer\n'
            'Final Answer: the final answer to the original input question\n'
            'Begin!\n\n'
            'history: {history}\n\n'
            'Question: {input}\n\n'
            'Thought: {agent_scratchpad}\n',

        # --- Turkish ---
        "tr":
            'Aşağıdaki soruları elinizden geldiğince yanıtlayın. Uygunsa bazı araçları kullanabilirsiniz. '
            'Aşağıdaki araçlara erişiminiz var:\n\n'
            '{tools}\n\n'
            'Aşağıdaki formatı kullanın:\n'
            'Soru: yanıtlamanız gereken giriş sorusu\n'
            'Düşünce: her zaman ne yapacağınızı ve hangi araçları kullanacağınızı düşünmelisiniz.\n'
            'Eylem: yapılacak eylem, [{tool_names}] arasından biri olmalıdır\n'
            'Eylem Girdisi: eylemin girdisi\n'
            'Gözlem: eylemin sonucu\n'
            '... (bu Düşünce/Eylem/Eylem Girdisi/Gözlem sıfır veya daha fazla kez tekrarlanabilir)\n'
            'Düşünce: Artık son cevabı biliyorum\n'
            'Son Cevap: orijinal giriş sorusuna verilen son cevap\n'
            'Başla!\n\n'
            'geçmiş: {history}\n\n'
            'Soru: {input}\n\n'
            'Düşünce: {agent_scratchpad}\n',
    }
}
