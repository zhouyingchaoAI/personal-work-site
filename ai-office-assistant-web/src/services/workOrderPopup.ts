import { ref } from 'vue'

export const workOrderPopup = ref<{ ticketId: string } | null>(null)
export function openWorkOrderPopup(ticketId = '') {
  workOrderPopup.value = { ticketId }
}
