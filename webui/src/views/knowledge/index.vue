<template>
  <div class="columnSC" style="width: 100%">
    <div class="rowBC" style="padding: 20px; width: 100%">
      <div style="font-size: 24px; color: var(--el-text-color-primary)">{{ $t('KnowledgeListTitle') }}</div>
      <el-button size="default" plain type="primary" @click="onCreateKnowledgeClick">{{ $t('KnowledgeCreteButtonTitle') }}</el-button>
    </div>

    <div class="rowSC wrap knowledges-container" style="padding: 10px 20px; width: 100%">
      <div v-for="(item, index) in knowledge.list" :key="index" class="knowledge-container" @click="onKnowledgeClick(item)">
        <div class="rowBC">
          <div class="title rowSC">
            <el-icon style="margin-right: 5px;" size="20" color="var(--el-color-primary)">
              <Notebook/>
            </el-icon>
            <span>{{ item.kb_name }}</span>
          </div>
          <el-tag size="small" style="margin-left: 5px;">{{ item.embed_model }}</el-tag>
        </div>
        <div class="desc">
          {{ item.kb_info }}
        </div>
        <div class="rowSC wrap">
          <div v-for="(vs_item, vs_index) in item.vs_types" :key="vs_index" style="margin-right: 16px">
            <el-tag size="small" style="margin-bottom: 5px">{{ vs_item.vs_type }}</el-tag>
            <span style="color: var(--el-text-color-regular); margin: 0 2px">/</span>
            <el-tag size="small" style="margin-bottom: 5px">{{vs_item.file_count}} {{ $t('kbFiles') }}</el-tag>
          </div>
        </div>
      </div>
    </div>

    <el-dialog v-model="dialogCreateFormVisible" :title="$t('createKnowledgeBase')" width="800" destroy-on-close>
      <el-form ref="ruleFormRef" :model="createForm" label-width="160">
        <el-form-item :label="$t('name')" prop="kb_name" :rules="[{required: true, message: $t('pleaseInputName'), trigger: 'blur'}]">
          <el-input v-model="createForm.kb_name" />
        </el-form-item>
        <el-form-item :label="$t('briefIntroduction')" prop="kb_info" :rules="[{required: true, message: $t('pleaseInputBriefIntroduction'), trigger: 'blur'}]">
          <el-input v-model="createForm.kb_info" :rows="2" type="textarea"/>
        </el-form-item>
        <el-form-item :label="$t('embeddingModel')" prop="model" :rules="[{required: true, message: $t('pleaseSelectEmbeddingModel'), trigger: 'blur, change'}]">
          <el-select v-model="createForm.model" :placeholder="$t('pleaseSelectEmbeddingModel')" style="width: 100%" filterable allow-create default-first-option>
            <el-option label="all-MiniLM-L6-v2" value="all-MiniLM-L6-v2" />
            <el-option label="all-MiniLM-L12-v2" value="all-MiniLM-L12-v2" />
            <el-option label="all-mpnet-base-v2" value="all-mpnet-base-v2" />
            <el-option label="paraphrase-multilingual-MiniLM-L12-v2" value="paraphrase-multilingual-MiniLM-L12-v2" />
            <el-option label="paraphrase-multilingual-mpnet-base-v2" value="paraphrase-multilingual-mpnet-base-v2" />
            <el-option label="text-embedding-ada-002 (OpenAI)" value="text-embedding-ada-002" />
            <el-option label="text-embedding-3-small (OpenAI)" value="text-embedding-3-small" />
            <el-option v-for="item in embedList.value" :key="item" :label="item" :value="item" />
          </el-select>
          <div class="form-hint">{{ $t('kbSettingsEmbeddingModelHint') }}</div>
        </el-form-item>

        <!-- ─── Ek Ayarlar (Collapsible) ─── -->
        <el-divider content-position="left">
          <el-button link type="primary" size="small" @click="showAdvancedCreate = !showAdvancedCreate">
            ⚙️ {{ $t('kbAdvancedSettings') }}
            <el-icon style="margin-left: 4px;" :class="{ 'rotate-icon': showAdvancedCreate }"><ArrowDown /></el-icon>
          </el-button>
        </el-divider>
        <Transition name="kb-settings-slide">
          <div v-show="showAdvancedCreate">
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item :label="$t('kbSettingsDefaultKb')">
                  <el-input v-model="kbSettings.default_knowledge_base" :placeholder="$t('kbSettingsDefaultKbPlaceholder')" clearable />
                  <div class="form-hint">{{ $t('kbSettingsDefaultKbHint') }}</div>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item :label="$t('kbSettingsMaxContextBytes')">
                  <el-input-number v-model="kbSettings.vs_type_prompt_total_byte_size" :min="500" :max="50000" :step="500" style="width: 100%" controls-position="right" />
                  <div class="form-hint">{{ $t('kbSettingsMaxContextBytesHint') }}</div>
                </el-form-item>
              </el-col>
            </el-row>
          </div>
        </Transition>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="dialogCreateFormVisible = false">{{ $t('cancel') }}</el-button>
          <el-button type="primary" @click="onCreateClick()" :loading="savingSettings">
            {{ $t('create') }}
          </el-button>
        </div>
      </template>
    </el-dialog>

  </div>
</template>

<script setup lang="ts" name="Knowledge">

import {knowledgeListReq, llmModelEmbedModelsReq, createKnowledgeBaseReq, getKbSettingsReq, saveKbSettingsReq} from "@/api/knowledge";
import {ElMessage} from "element-plus";
import { reactive, ref, onMounted } from 'vue'
import {useRouter} from 'vue-router'
import {useI18n} from 'vue-i18n'

const router = useRouter()
const { t } = useI18n()

const knowledge: Ref<Array<object>>  =  reactive({list: []});

const embedList: Ref<Array<string>> = reactive([])

const ruleFormRef = ref<FormInstance>()

const dialogCreateFormVisible = ref(false)

// ── KB create dialog advanced section ──
const showAdvancedCreate = ref(false)
const savingSettings = ref(false)
const kbSettings = reactive({
  embedding_model: 'all-MiniLM-L6-v2',
  default_knowledge_base: 'samples',
  vs_type_prompt_total_byte_size: 3000,
})

const createForm = reactive({
  kb_name: '',
  kb_info: '',
  model: 'all-MiniLM-L6-v2'
})


onMounted(() => {
  getKnowledgeList()
  getEmbedModels()
  fetchKbSettings()
});

const getKnowledgeList = async () => {
  const res = await knowledgeListReq();
  knowledge.list = mergeSameKb(res.data)
}

const mergeSameKb = (data) => {
  const mergedDataMap = {}
  data.forEach(item => {
    const key = item.kb_name;
    if (!mergedDataMap[key]) {
      mergedDataMap[key] = {
        kb_name: key,
        kb_info: item.kb_info,
        embed_model: item.embed_model,
        create_time: item.create_time,
        vs_types: [{vs_type: item.vs_type, file_count: item.file_count}]
      };
    } else {
      mergedDataMap[key].vs_types.push({vs_type: item.vs_type, file_count: item.file_count});
    }
  });
  return mergedDataMap ? Object.values(mergedDataMap) : [];
}

const getEmbedModels = async () => {
  embedList.value = []
  llmModelEmbedModelsReq().then(res => {
    embedList.value = res.data;
  })
}

const fetchKbSettings = async () => {
  try {
    const res = await getKbSettingsReq()
    if (res.code === 200 && res.data) {
      kbSettings.embedding_model = res.data.embedding_model || 'all-MiniLM-L6-v2'
      kbSettings.default_knowledge_base = res.data.default_knowledge_base || 'samples'
      kbSettings.vs_type_prompt_total_byte_size = res.data.vs_type_prompt_total_byte_size ?? 3000
    }
  } catch (e) {
    console.error(e)
  }
}

const onCreateKnowledgeClick = () => {
  createForm.kb_name = ''
  createForm.kb_info = ''
  createForm.model = kbSettings.embedding_model || 'all-MiniLM-L6-v2'
  showAdvancedCreate.value = false
  dialogCreateFormVisible.value = true
}

const onKnowledgeClick = (item) => {
  router.push({path: '/knowledge/detail', query: {kb_name: item.kb_name}})
}

const onCreateClick = () => {
  ruleFormRef.value.validate(async (valid) => {
    if (valid) {
      savingSettings.value = true
      try {
        // Save embedding settings if they were changed
        await saveKbSettingsReq({
          embedding_model: createForm.model,
          default_knowledge_base: kbSettings.default_knowledge_base,
          vs_type_prompt_total_byte_size: kbSettings.vs_type_prompt_total_byte_size,
        })
        // Update local state
        kbSettings.embedding_model = createForm.model

        // Create the knowledge base
        await createKnowledgeBaseReq(createForm.kb_name, createForm.kb_info, createForm.model)
        dialogCreateFormVisible.value = false
        ElMessage({
          type: 'success',
          message: t('createSuccessfully'),
        })
        getKnowledgeList()
      } catch (e) {
        console.error(e)
        ElMessage.error(t('createFailed') || 'Create failed')
      } finally {
        savingSettings.value = false
      }
    } else {
      return false
    }
  })
}


</script>

<style>
.knowledge-container:hover {
  box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.01);
  border-color: var(--el-color-primary);
  transform: translateY(-2px);
}

.knowledges-container {
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  grid-gap: 20px;
}

/* ── Form hint ── */
.form-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
  line-height: 1.4;
}
.rotate-icon {
  transform: rotate(180deg);
  transition: transform 0.3s ease;
}
.el-icon {
  transition: transform 0.3s ease;
}

/* ── Settings slide transition ── */
.kb-settings-slide-enter-active,
.kb-settings-slide-leave-active {
  transition: all 0.3s ease;
  overflow: hidden;
}
.kb-settings-slide-enter-from,
.kb-settings-slide-leave-to {
  max-height: 0;
  opacity: 0;
  padding-top: 0;
  padding-bottom: 0;
}
.kb-settings-slide-enter-to,
.kb-settings-slide-leave-from {
  max-height: 400px;
  opacity: 1;
}
</style>

<style lang="scss">
.knowledge-container {
  flex: 1 1 280px;
  height: 140px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 16px;
  cursor: pointer;
  background: var(--el-bg-color);
  display: flex;
  flex-direction: column;
  padding: 16px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);

  .title {
    font-size: 16px;
    color: var(--el-text-color-primary);
    font-weight: 600;
  }

  .desc {
    font-size: 13px;
    color: var(--el-text-color-secondary);
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    overflow: hidden;
    margin: 12px 0;
    flex-shrink: 0;
    line-height: 1.5;
  }
}
</style>
