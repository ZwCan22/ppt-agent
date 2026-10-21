<script setup lang="ts">
const props = withDefaults(defineProps<{
  name: 'slides' | 'sparkles' | 'arrow' | 'download' | 'check' | 'clock' | 'loader' | 'chevron' | 'file'
  size?: number
}>(), { size: 20 })

const paths = {
  slides: ['M5 4h14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z', 'M7 9h10M7 13h7M7 17h4'],
  sparkles: ['m12 3 2.3 6.7L21 12l-6.7 2.3L12 21l-2.3-6.7L3 12l6.7-2.3L12 3Z', 'M20 2v4M18 4h4'],
  arrow: ['M4 12h15', 'm13 6 6 6-6 6'],
  download: ['M12 3v12', 'm7 10 5 5 5-5', 'M4 16v4h16v-4'],
  check: ['m5 12 4 4L19 6'],
  clock: ['M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z', 'M12 7v5l3 2'],
  loader: ['M21 12a9 9 0 1 1-9-9'],
  chevron: ['m9 5 7 7-7 7'],
  file: ['M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6Z', 'M14 2v6h6', 'M8 13h8M8 17h5'],
} as const
</script>

<template>
  <svg :width="props.size" :height="props.size" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"
    aria-hidden="true" focusable="false">
    <path v-for="(path, index) in paths[props.name]" :key="index" :d="path" />
  </svg>
</template>
