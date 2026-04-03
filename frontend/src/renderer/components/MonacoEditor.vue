<template>
  <div ref="containerRef" class="monaco-editor-host"></div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';
import * as monaco from 'monaco-editor/esm/vs/editor/editor.api';
import 'monaco-editor/esm/vs/basic-languages/python/python.contribution';

import editorWorker from 'monaco-editor/esm/vs/editor/editor.worker?worker';

if (!globalThis.MonacoEnvironment) {
  globalThis.MonacoEnvironment = {
    getWorker() {
      return new editorWorker();
    },
  };
}

const props = defineProps({
  modelValue: {
    type: String,
    default: '',
  },
  language: {
    type: String,
    default: 'python',
  },
  readOnly: {
    type: Boolean,
    default: false,
  },
  theme: {
    type: String,
    default: 'vs-dark',
  },
  options: {
    type: Object,
    default: () => ({}),
  },
});

const emit = defineEmits(['update:modelValue', 'ready']);

const containerRef = ref(null);
let editor = null;
let suppressEmit = false;

const buildEditorOptions = () => ({
  value: props.modelValue || '',
  language: props.language,
  theme: props.theme,
  readOnly: props.readOnly,
  automaticLayout: true,
  minimap: { enabled: false },
  fontSize: 13,
  lineNumbersMinChars: 3,
  scrollBeyondLastLine: false,
  tabSize: 2,
  wordWrap: 'on',
  ...props.options,
});

onMounted(() => {
  if (!containerRef.value) return;

  editor = monaco.editor.create(containerRef.value, buildEditorOptions());
  editor.onDidChangeModelContent(() => {
    if (suppressEmit) return;
    emit('update:modelValue', editor.getValue());
  });
  emit('ready', editor);
});

watch(
  () => props.modelValue,
  (value) => {
    if (!editor || value === editor.getValue()) return;
    suppressEmit = true;
    editor.setValue(value || '');
    suppressEmit = false;
  }
);

watch(
  () => props.readOnly,
  (value) => {
    editor?.updateOptions({ readOnly: value });
  }
);

watch(
  () => props.language,
  (value) => {
    const model = editor?.getModel();
    if (model && value) {
      monaco.editor.setModelLanguage(model, value);
    }
  }
);

watch(
  () => props.theme,
  (value) => {
    if (value) {
      monaco.editor.setTheme(value);
    }
  }
);

onBeforeUnmount(() => {
  editor?.dispose();
});
</script>

<style scoped>
.monaco-editor-host {
  width: 100%;
  height: 100%;
  min-height: 420px;
  border-radius: 14px;
  overflow: hidden;
  background: #111827;
}
</style>
