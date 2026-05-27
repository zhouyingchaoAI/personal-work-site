<script setup lang="ts">
import './index.scss'

type ButtonIcon = 'plus' | 'sparkle' | 'history' | 'download' | 'refresh' | 'copy' | 'send'
type ButtonVariant = 'outline' | 'primary'
type ButtonSize = 'sm' | 'md'

const props = withDefaults(
  defineProps<{
    icon: ButtonIcon
    variant?: ButtonVariant
    size?: ButtonSize
    block?: boolean
    nativeType?: 'button' | 'submit' | 'reset'
    disabled?: boolean
  }>(),
  {
    variant: 'outline',
    size: 'sm',
    block: false,
    nativeType: 'button',
    disabled: false,
  },
)
</script>

<template>
  <button
    :type="props.nativeType"
    :disabled="props.disabled"
    :class="[
      'icon-text-button',
      `icon-text-button--${props.variant}`,
      `icon-text-button--${props.size}`,
      { 'icon-text-button--block': props.block },
    ]"
  >
    <span class="icon-text-button__icon" aria-hidden="true">
      <svg v-if="props.icon === 'plus'" viewBox="0 0 16 16" focusable="false">
        <path d="M8 3.5v9" />
        <path d="M3.5 8h9" />
      </svg>
      <svg
        v-else-if="props.icon === 'sparkle'"
        class="icon-text-button__svg--fill"
        viewBox="0 0 16 16"
        focusable="false"
      >
        <path d="M7.2 2.2 8.4 5.6l3.4 1.2-3.4 1.2-1.2 3.4L6 8 2.6 6.8 6 5.6Z" />
        <path d="M12.3 9.9 12.8 11l1.1.5-1.1.5-.5 1.1-.5-1.1-1.1-.5 1.1-.5Z" />
      </svg>
      <svg v-else-if="props.icon === 'history'" viewBox="0 0 16 16" focusable="false">
        <path d="M4.2 5.4a4.8 4.8 0 1 1 .9 5.5" />
        <path d="M4.1 2.8v2.8h2.8" />
        <path d="M8 5.2v3.2l2.1 1.2" />
      </svg>
      <svg v-else-if="props.icon === 'download'" viewBox="0 0 16 16" focusable="false">
        <path d="M8 2.8v6.7" />
        <path d="m5.2 6.9 2.8 2.8 2.8-2.8" />
        <path d="M3.2 12.6h9.6" />
      </svg>
      <svg v-else-if="props.icon === 'refresh'" viewBox="0 0 16 16" focusable="false">
        <path d="M12.7 5.6A4.8 4.8 0 0 0 4 4.5L3.2 6.1" />
        <path d="M3.1 3.6v2.7h2.7" />
        <path d="M3.3 10.4A4.8 4.8 0 0 0 12 11.5l.8-1.6" />
        <path d="M12.9 12.4V9.7h-2.7" />
      </svg>
      <svg v-else-if="props.icon === 'copy'" viewBox="0 0 16 16" focusable="false">
        <rect x="5.4" y="4.2" width="7" height="8.2" rx="1.2" />
        <path d="M3.6 10.2V3.8c0-.7.5-1.2 1.2-1.2h5.4" />
      </svg>
      <svg v-else viewBox="0 0 16 16" focusable="false">
        <path d="M2.7 7.8 13.2 3.1 10 13.2 7.8 8.8Z" />
        <path d="m7.8 8.8 2.9-2.9" />
      </svg>
    </span>
    <span class="icon-text-button__label">
      <slot />
    </span>
  </button>
</template>
