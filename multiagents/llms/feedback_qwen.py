from . import llm_registry
from .qwen_vllm import QwenVllmChat
from .doc_kb import DocKnowledgeBase
from .feedback_openai import get_cur_task, get_time
import copy
from multiagents.utils.interact import (user_input, add_display_message, add_edit_message, add_feedback_message,
                                        finish_feedback_message, finish_select_edit_message)

# {preferred_output}
# """

JUDGE_FEEDBACK_PROMPT_zh = "You will receive user feedback on a response. Please judge whether it includes any suggestions on how to improve the content or format of the response.\nOnly answer yes or no."


@llm_registry.register('feedback_qwen')
class FeedbackQwenChat(QwenVllmChat):
    kb: DocKnowledgeBase = None
    feedbacks: list = []

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.enable_feedback = True
        self.kb = DocKnowledgeBase(knowledge_base_name='feedback_qwen')

    def feedback(self, messages, instruction, output, feedback):
        messages = copy.deepcopy(messages)
        # instruction_feedback = f'{instruction}\n\n{feedback}'
        messages.append({"role": "assistant", "content": output})
        messages.append({"role": "user", "content": feedback})
        reply = self.chat(messages)

        return reply

    def extract_rules_from_feedback(self, messages, output, preferred_output):
        raise NotImplementedError

    def judge_feedback(self, feedback):
        judge_messages = [{'role': 'system', 'content': JUDGE_FEEDBACK_PROMPT_zh},
                          {'role': 'user', 'content': feedback}]
        reply = self.chat(judge_messages)
        return "yes" in reply.lower() or "evet" in reply.lower()

    def interact(self, instruction, res, role, task):
        cur_task = get_cur_task(task)
        print('=' * 10 + 'INPUT' + '=' * 10, flush=True)
        print(self.conversation_history, flush=True)
        print('=' * 10 + 'OUTPUT' + '=' * 9, flush=True)
        print(res, flush=True)
        print('=' * 25, flush=True)
        feedback_placeholder = "Please enter your feedback on the Anomivox response (e.g., you must reply in xxx format; regarding xxx, you should provide more details)."
        add_feedback_message(cur_task, role, feedback_placeholder, res['content'], get_time())
        feedback = user_input(feedback_placeholder + '\n')
        finish_feedback_message()
        if feedback.strip() == '' or feedback.lower() == 'continue' or not self.judge_feedback(feedback):
            empty_feedback_placeholder = 'No feedback / Invalid feedback, diagnosis continues.'
            add_display_message(cur_task, role, empty_feedback_placeholder, get_time())
            return None

        refined_reply = self.feedback(self.conversation_history, instruction, res['content'], feedback)

        if refined_reply is not None:
            print('=' * 6 + 'REFINED OUTPUT' + '=' * 6, flush=True)
            print(refined_reply, flush=True)
            print('=' * 25, flush=True)
            eval_placeholder = "Are you satisfied with the improved answer? Please only answer \"yes\" or \"no\"."
            add_feedback_message(cur_task, role, eval_placeholder, refined_reply, get_time())
            eval_ = user_input(eval_placeholder + '\n')
            finish_feedback_message()
            if "no" in eval_.lower() or "no" in eval_.lower() or "no" in eval_.lower():
                refine_placeholder = 'Please enter in detail what you think the correct answer is.'
                add_edit_message(cur_task, role, refine_placeholder, res['content'], get_time())
                refined_reply = user_input(refine_placeholder + '\n')
                self.feedbacks.append(
                    {"feedback": feedback, "refined_response": refined_reply, "auto": False, "task": task})
                finish_select_edit_message(cur_task, role)
            else:
                self.feedbacks.append(
                    {"feedback": feedback, "refined_response": refined_reply, "auto": True, "task": task})
                finish_feedback_message()
        else:
            print('=' * 10 + 'OUTPUT' + '=' * 9, flush=True)
            print(res, flush=True)
            print('=' * 25, flush=True)
            refine_placeholder = "Sorry, we were unable to improve the answer based on your feedback. Please enter in detail what you think the correct answer is."
            add_edit_message(cur_task, role, refine_placeholder, res['content'], get_time())
            refined_reply = user_input(refine_placeholder + '\n')
            self.feedbacks.append(
                {"feedback": feedback, "refined_response": refined_reply, "auto": False, "task": task})
            finish_select_edit_message(cur_task, role)

        return refined_reply

    def remove_conflict_identical(self, new_doc, relevant_doc):
        raise NotImplementedError

    def parse(self, role="", task=""):
        res = super().parse(role=role, task=task)

        if task in ['expert_root_cause', 'expert_solution', 'review', 'refine_root_cause', 'refine_solution']:
            refined_reply = self.interact("", res, role, task)
            if refined_reply is not None:
                res['content'] = refined_reply

        return res
