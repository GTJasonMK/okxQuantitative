<template>
  <div ref="containerRef" class="monaco-editor-host"></div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';

let monacoRuntimePromise = null;

const loadMonacoRuntime = async () => {
  if (!monacoRuntimePromise) {
    monacoRuntimePromise = Promise.all([
      import('monaco-editor/esm/vs/editor/editor.api'),
      import('monaco-editor/esm/vs/basic-languages/python/python.contribution'),
      import('monaco-editor/esm/vs/editor/editor.worker?worker'),
    ]).then(([monacoModule, _pythonContribution, workerModule]) => {
      const EditorWorker = workerModule.default;
      if (!globalThis.MonacoEnvironment) {
        globalThis.MonacoEnvironment = {
          getWorker() {
            return new EditorWorker();
          },
        };
      }
      return monacoModule;
    });
  }
  return monacoRuntimePromise;
};

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
let monacoApi = null;
let suppressEmit = false;
let unmounted = false;

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

onMounted(async () => {
  monacoApi = await loadMonacoRuntime();
  if (!containerRef.value || unmounted) return;

  editor = monacoApi.editor.create(containerRef.value, buildEditorOptions());
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
    if (model && value && monacoApi?.editor) {
      monacoApi.editor.setModelLanguage(model, value);
    }
  }
);

watch(
  () => props.theme,
  (value) => {
    if (value && monacoApi?.editor) {
      monacoApi.editor.setTheme(value);
    }
  }
);

onBeforeUnmount(() => {
  unmounted = true;
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
